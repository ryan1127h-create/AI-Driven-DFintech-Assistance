"""JSON API endpoints for the React/Vite frontend.

The React app never reads local secret files directly.  It posts form data to
these endpoints; the Python backend then parses files, reads data/.deepseek.json
through common.config, runs the existing agents, and returns UI-ready JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from common import config
from supervisor import default_intents_for, route

from . import profile_form as pf
from .extract_profile import ProfileExtractionError, extract_fields, parse_file

from pydantic import BaseModel, Field

from common.profile import ConsentFlags, LifecycleStage, Proficiency, TargetRole, UserProfile, WorkDomain

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

_SECTION_KEYS = {
    "generate_application_checklist": "checklist",
    "get_application_status": "tracker",
    "compare_programs": "comparison",
    "recommend_courses": "recommendation",
    "recommend_career_path": "career",
}

_PRIORITY_WEIGHTS = {
    "role_fit": {"role_fit": 1.0},
    "cost": {"cost": 0.7, "role_fit": 0.3},
    "duration": {"duration": 0.7, "role_fit": 0.3},
}

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_MODULE_CATALOG = _DATA_DIR / "module_catalog.json"


DEFAULT_API_USER_ID = "api_user"


class RecommendationProfileInput(BaseModel):
    """Wire shape accepted by the standalone recommendation endpoints.

    Transport only -- the one authority profile is common.profile.UserProfile,
    which _profile_from_recommendation_request builds from this. Every field is
    typed with the authority's own vocabulary, so an unrecognised value is
    rejected here (422, echoing the offending value) instead of being quietly
    coerced to a default or dropped to None.
    """

    user_id: str = DEFAULT_API_USER_ID
    lifecycle_stage: LifecycleStage = LifecycleStage.current
    target_roles: list[TargetRole] = Field(default_factory=list)
    target_role: TargetRole | None = None
    completed_modules: list[str] | str = Field(default_factory=list)
    technical_proficiency: Proficiency | None = None
    finance_knowledge: Proficiency | None = None
    work_domain: WorkDomain | None = None
    # Opt-IN, matching ConsentFlags.personalization. A caller who omits the key
    # has expressed no consent, so this must default OFF -- defaulting to True
    # here would personalise every request that never mentioned personalisation,
    # which is the privacy-default inversion the authority model exists to prevent.
    personalization: bool = False


class RecommendationRequest(BaseModel):
    profile: RecommendationProfileInput
    target_role: TargetRole | None = None


def _json_error(message: str, status: int = 500) -> JSONResponse:
    """Uniform JSON error response, in the shape the routes already return."""
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


def _module_sources() -> dict[str, str | None]:
    if not _MODULE_CATALOG.exists():
        return {}
    try:
        data = json.loads(_MODULE_CATALOG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        str(m.get("code", "")).upper(): m.get("source_url")
        for m in data.get("modules", [])
        if m.get("code")
    }


def _normalise_completed_modules(raw: list[str] | str) -> list[str]:
    if isinstance(raw, str):
        pieces = raw.replace(";", ",").split(",")
    else:
        pieces = raw or []
    return [str(code).strip().upper() for code in pieces if str(code).strip()]


def _ordered_target_roles(
    roles: list[TargetRole], override: TargetRole | None
) -> list[TargetRole]:
    """Order-preserving, de-duplicated roles; an explicit override leads the list.

    Index 0 is the primary role by the authority's own convention: it is what
    navigator.pick_primary_role advises on and what
    common.profile_adapter.to_rag_data emits into their single `target_role_std`
    slot. An override already present in `roles` is moved to the front rather
    than left where it was -- otherwise "explicit override" would only win for
    users who had not already listed that role.
    """
    leading = [override] if override else []
    return list(dict.fromkeys([*leading, *roles]))


def _profile_from_recommendation_request(payload: RecommendationRequest) -> UserProfile:
    """Build the authority profile from an already-validated wire request.

    No value mapping happens here: RecommendationProfileInput has already
    rejected anything outside the authority vocabulary, including the stage. An
    `alumni` request therefore stays `alumni` and gets the alumni-flow answer
    from the supervisor, rather than being advised as a current student.

    An explicit `target_role` is carried on the profile itself, at the head of
    `target_roles`, and nowhere else. It used to be passed to the agents a second
    time as a `target_role` slot, which `pick_primary_role` reads first; that
    duplicate shadowed the ordering above entirely, so the profile could disagree
    with the role actually advised on and nothing would notice.
    """
    incoming = payload.profile
    override = payload.target_role or incoming.target_role
    return UserProfile(
        user_id=incoming.user_id,
        lifecycle_stage=incoming.lifecycle_stage,
        authenticated=True,
        work_domain=incoming.work_domain,
        technical_proficiency=incoming.technical_proficiency,
        finance_knowledge=incoming.finance_knowledge,
        target_roles=_ordered_target_roles(incoming.target_roles, override),
        completed_modules=_normalise_completed_modules(incoming.completed_modules),
        consent_flags=ConsentFlags(personalization=incoming.personalization),
    )


def _material_to_dict(material: pf.UploadedMaterial) -> dict:
    status = "uploaded" if material.status == "submitted" else material.status
    return {
        "key": material.key,
        "label": material.label,
        "required": material.required,
        "filename": material.filename,
        "status": status,
        "reason": material.reason,
        "size_bytes": material.size_bytes,
        "view_url": material.view_url,
    }


def _material_summary(materials: list[pf.UploadedMaterial]) -> dict:
    summary = pf.material_summary(materials) if materials else {
        "required_total": 0,
        "submitted_required": 0,
        "missing_required": 0,
        "rejected_required": 0,
        "is_complete": False,
    }
    return {
        "requiredTotal": summary["required_total"],
        "submittedRequired": summary["submitted_required"],
        "missingRequired": summary["missing_required"],
        "rejectedRequired": summary["rejected_required"],
        "isComplete": summary["is_complete"],
    }


def _checklist(resp) -> list[dict]:
    items = (getattr(resp, "data", {}) or {}).get("items", []) if resp else []
    return [
        {
            "key": item.get("key"),
            "label": item.get("label"),
            "required": item.get("required", False),
            "status": item.get("status_label") or item.get("status"),
            "why": item.get("why"),
            "deadline": item.get("deadline"),
            "urgency": item.get("urgency"),
        }
        for item in items
    ]


def _timeline(resp) -> list[dict]:
    data = (getattr(resp, "data", {}) or {}) if resp else {}
    return data.get("demo_milestones") or [
        {"label": "Fill in profile", "state": "done"},
        {"label": "Upload application materials", "state": "current"},
        {"label": "Material completeness check", "state": "pending"},
        {"label": "Formal academic review", "state": "pending"},
        {"label": "Admission decision", "state": "pending"},
    ]


def _comparison(resp) -> list[dict]:
    rows = (((getattr(resp, "data", {}) or {}).get("facts_table") or {}).get("rows") or []) if resp else []
    out = []
    for row in rows:
        facts = row.get("facts", {})

        def cell(dim: str) -> str:
            raw = facts.get(dim) or {}
            return raw.get("text") or "Not published"

        out.append({
            "program": row.get("program"),
            "is_target": row.get("is_target", False),
            "duration": cell("duration"),
            "fees": cell("fees"),
            "format": cell("format"),
            "source_url": row.get("source_url"),
            "fetched_at": row.get("fetched_at"),
            "facts": facts,
        })
    return out


def _recommendation(resp) -> dict:
    data = (getattr(resp, "data", {}) or {}) if resp else {}
    sources = _module_sources()
    recommended = []
    for mod in data.get("recommended", []) or []:
        code = str(mod.get("code", "")).upper()
        row = dict(mod)
        row["code"] = code
        row["credits"] = row.get("credits") or 4
        row["source_url"] = row.get("source_url") or sources.get(code)
        recommended.append(row)

    progress = data.get("graduation_progress") or {}
    return {
        "recommended": recommended,
        "skillGaps": data.get("skill_gaps") or [],
        "progress": {
            "completed": progress.get("completed_credits", 0),
            "planned": progress.get("planned_credits", sum((m.get("credits") or 4) for m in recommended)),
            "required": progress.get("required", 52),
            "remaining": progress.get("remaining", max(0, 52 - sum((m.get("credits") or 4) for m in recommended))),
            "courseworkRequired": progress.get("coursework_required", 40),
            "capstoneRequired": progress.get("capstone_required", 12),
        },
        "courseExplanation": data.get("explanation") or getattr(resp, "speakable", ""),
        "prereqWarnings": data.get("prereq_warnings") or [],
        "studyPlans": data.get("study_plans") or {},
        "unrecognizedCompleted": data.get("unrecognized_completed") or [],
    }


def _career(resp) -> dict:
    data = (getattr(resp, "data", {}) or {}) if resp else {}
    return {
        "careerAdvice": data.get("explanation") or getattr(resp, "speakable", ""),
        "targetRole": data.get("target_role"),
        "requiredSkills": data.get("required_skills") or [],
        "matchedSkills": data.get("matched_skills") or [],
        "skillsFromCourses": data.get("skills_from_courses") or [],
        "careerSkillGaps": data.get("skill_gaps") or [],
        "gapClosingModules": data.get("gap_closing_modules") or [],
        "selectionSource": data.get("selection_source"),
        "unrecognizedCompleted": data.get("unrecognized_completed") or [],
    }


def _agent_status(resp) -> dict:
    return {
        "status": resp.status,
        "answer_type": resp.answer_type,
        "speakable": resp.speakable,
        "missing_fields": resp.missing_fields,
        "sources": resp.sources,
    }


def _react_payload(profile, results: dict, material_analysis: list[pf.UploadedMaterial]) -> dict:
    recommendation = _recommendation(results.get("recommendation"))
    career = _career(results.get("career"))
    completed_codes = list(profile.completed_modules or [])
    payload = {
        "profileType": profile.lifecycle_stage.value,
        "profile": {
            "lifecycle_stage": profile.lifecycle_stage.value,
            "completed_modules": completed_codes,
            "target_roles": [r.value for r in profile.target_roles],
            "technical_proficiency": profile.technical_proficiency.value if profile.technical_proficiency else None,
            "finance_knowledge": profile.finance_knowledge.value if profile.finance_knowledge else None,
        },
        "materialSummary": _material_summary(material_analysis),
        "materials": [_material_to_dict(m) for m in material_analysis],
        "checklist": _checklist(results.get("checklist")),
        "timeline": _timeline(results.get("tracker")),
        "comparison": _comparison(results.get("comparison")),
        "recommended": recommendation["recommended"],
        "completedCodes": completed_codes,
        "skillGaps": recommendation["skillGaps"],
        "progress": recommendation["progress"],
        "courseExplanation": recommendation["courseExplanation"],
        "prereqWarnings": recommendation["prereqWarnings"],
        "studyPlans": recommendation["studyPlans"],
        "unrecognizedCompleted": recommendation["unrecognizedCompleted"],
        **career,
        "agentStatus": {
            key: {
                "status": resp.status,
                "answer_type": resp.answer_type,
                "speakable": resp.speakable,
                "missing_fields": resp.missing_fields,
            }
            for key, resp in results.items()
        },
    }
    return payload

router = APIRouter()


# def register_api(app, upload_root: Path) -> None:
@router.get("/health")
async def api_health():
    return {"ok": True, "settings": config.status()}

@router.get("/settings/status")
async def api_settings_status():
    return {"ok": True, "status": config.status()}

@router.post("/settings")

async def api_settings_save(request: Request):
    body = await request.json()
    # body = request.get_json(silent=True) or {}
    action = body.get("action", "save")
    key = (body.get("api_key") or "").strip()
    model = (body.get("model") or "").strip()
    base_url = (body.get("base_url") or "").strip()
    if key or model or base_url:
        config.set_credentials(api_key=key or None, model=model or None, base_url=base_url or None)
    if action == "test":
        ok, message = config.test_connection()
    else:
        ok, message = True, "Saved."
    return {"ok": ok, "message": message, "status": config.status()}

@router.post("/extract-profile")
async def api_extract_profile(
    lifecycle_stage: str = Form("applicant"),
    text: str = Form(""),
    cv: UploadFile = File(None),
):
    try:
        selected_stage = pf.normalize_stage(lifecycle_stage).value

        cv_name = ""

        if cv and cv.filename:
            cv_name = cv.filename
            content = await cv.read()
            text = parse_file(cv.filename, content)

        prefill = extract_fields(text) if text else {}

        prefill["lifecycle_stage"] = selected_stage

        if cv_name:
            prefill["_cv_name"] = cv_name
        if text:
            prefill["_raw_text_chars"] = len(text)

        return {
            "ok": True,
            "prefill": prefill,
            "settings": config.status(),
        }

    except Exception as exc:
        return _json_error(str(exc))


@router.post("/advise")
async def api_advise(request: Request):
    try:
        form = await request.form()

        selected_stage = pf.normalize_stage(form.get("lifecycle_stage", "applicant"))
        upload_token = uuid4().hex

        # ⚠️ FastAPI form/file handling
        material_analysis = pf.analyse_uploaded_materials(
            form,
            selected_stage,
            save_dir=Path("./uploads"),
            token=upload_token,
        )

        profile = pf.build_profile(form, form, material_results=material_analysis)

        priorities = _PRIORITY_WEIGHTS.get(form.get("priority", "role_fit"))

        slots = {
            "compare_programs": {"priorities": priorities},
            "get_application_status": {},
            "recommend_courses": {},
            "recommend_career_path": {},
        }

        results = {}
        for intent in default_intents_for(profile):
            results[_SECTION_KEYS[intent]] = route(intent, profile, slots.get(intent))

        return {
            "ok": True,
            "data": _react_payload(profile, results, material_analysis),
        }

    except Exception as exc:
        return _json_error(str(exc))


@router.post("/recommend/courses")
async def api_recommend_courses(payload: RecommendationRequest):
    try:
        profile = _profile_from_recommendation_request(payload)
        resp = route("recommend_courses", profile)
        status = 200 if resp.status in {"ok", "need_clarification"} else 400
        return JSONResponse(
            status_code=status,
            content={
                "ok": resp.status == "ok",
                "data": _recommendation(resp),
                "agentStatus": _agent_status(resp),
            },
        )
    except Exception as exc:
        return _json_error(str(exc))


@router.post("/recommend/career")
async def api_recommend_career(payload: RecommendationRequest):
    try:
        profile = _profile_from_recommendation_request(payload)
        resp = route("recommend_career_path", profile)
        status = 200 if resp.status in {"ok", "need_clarification"} else 400
        return JSONResponse(
            status_code=status,
            content={
                "ok": resp.status == "ok",
                "data": _career(resp),
                "agentStatus": _agent_status(resp),
            },
        )
    except Exception as exc:
        return _json_error(str(exc))
