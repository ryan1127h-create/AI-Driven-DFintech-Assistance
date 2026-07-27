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


class RecommendationProfile(BaseModel):
    """Compact JSON profile accepted by standalone recommendation APIs."""

    user_id: str = "api_user"
    lifecycle_stage: str = "current"
    target_roles: list[str] = Field(default_factory=list)
    target_role: str | None = None
    completed_modules: list[str] | str = Field(default_factory=list)
    technical_proficiency: str | None = None
    finance_knowledge: str | None = None
    work_domain: str | None = None
    personalization: bool = True


class RecommendationRequest(BaseModel):
    profile: RecommendationProfile
    target_role: str | None = None


def _json_error(message: str, status: int = 400, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return {(payload), status}


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


def _enum_value(enum_cls, raw):
    raw = (raw or "").strip() if isinstance(raw, str) else raw
    if not raw:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        return None


def _normalise_completed_modules(raw: list[str] | str) -> list[str]:
    if isinstance(raw, str):
        pieces = raw.replace(";", ",").split(",")
    else:
        pieces = raw or []
    return [str(code).strip().upper() for code in pieces if str(code).strip()]


def _profile_from_recommendation_request(payload: RecommendationRequest) -> tuple[UserProfile, dict]:
    incoming = payload.profile
    roles: list[TargetRole] = []
    for raw in incoming.target_roles:
        role = _enum_value(TargetRole, raw)
        if role and role not in roles:
            roles.append(role)

    slot_role = payload.target_role or incoming.target_role
    role_override = _enum_value(TargetRole, slot_role)
    if role_override and role_override not in roles:
        roles.insert(0, role_override)

    stage = _enum_value(LifecycleStage, incoming.lifecycle_stage) or LifecycleStage.current
    if stage not in (LifecycleStage.current, LifecycleStage.graduating, LifecycleStage.applicant, LifecycleStage.prospect, LifecycleStage.admitted):
        stage = LifecycleStage.current

    profile = UserProfile(
        user_id=incoming.user_id,
        lifecycle_stage=stage,
        authenticated=True,
        work_domain=_enum_value(WorkDomain, incoming.work_domain),
        technical_proficiency=_enum_value(Proficiency, incoming.technical_proficiency),
        finance_knowledge=_enum_value(Proficiency, incoming.finance_knowledge),
        target_roles=roles,
        completed_modules=_normalise_completed_modules(incoming.completed_modules),
        consent_flags=ConsentFlags(personalization=incoming.personalization),
    )
    slots = {"target_role": role_override.value} if role_override else {}
    return profile, slots


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
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )
    
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
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )


@router.post("/recommend/courses")
async def api_recommend_courses(payload: RecommendationRequest):
    try:
        profile, slots = _profile_from_recommendation_request(payload)
        resp = route("recommend_courses", profile, slots)
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
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@router.post("/recommend/career")
async def api_recommend_career(payload: RecommendationRequest):
    try:
        profile, slots = _profile_from_recommendation_request(payload)
        resp = route("recommend_career_path", profile, slots)
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
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})
