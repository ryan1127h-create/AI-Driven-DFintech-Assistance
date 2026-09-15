"""
Course recommendation tool — orchestrator adapter for the
course_recommendation specialist domain (see
app/domains/specialist/course_recommendation/), which by design only ever
consumes one complete report and does no profile/knowledge-base lookups of
its own. Unlike every other adapter in this package, this one is NOT
thin: assembling that report from the current chat turn (profile facts,
the full course catalogue, current-intake curriculum rules, a resolved
role profile, and its curated course shortlist) is real business logic,
done here because course_recommendation's own isolation is deliberate and
stays untouched.

`course_catalog[].skills` comes from knowledge.module_skills (real
per-course tagging), `vertical` from knowledge.course_electives, and
`can_recommend`/`needs_review` are passed through from knowledge.courses
as-is. `prerequisite_text`/`corequisite_text`/`preclusion_text` use the
grad-student-only, already-cleaned columns rather than NUSMods' raw text,
which mixes in undergraduate-only conditions that never apply to a DFT
(Graduate Coursework) student.

`career_role_modules` (the curated role->course shortlist) is now wired in
as `curated_role_courses` — a soft scoring bonus in the domain's STAGE 5,
never a restriction. `preferences` (workload/style text) is not populated
here yet: nothing upstream of this tool currently extracts that from the
chat turn, so the domain runs with its safe "no preference signal" default.
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.interface import (
    list_career_role_modules,
    list_course_electives,
    list_courses,
    list_curriculum_rules,
    list_module_skills,
    resolve_role_profile,
)
from app.domains.profile.interface import get_profile
from app.domains.specialist.course_recommendation.interface import recommend_courses
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.structured_reply import render_structured_reply
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message

_FALLBACK_REPLY = (
    "I couldn't put together a reliable course recommendation right now. "
    "Please try again shortly."
)

COURSE_RECOMMENDATION_STYLE_PROMPT = """\
You are the Course Recommendation Advisor for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your role is to present a set of course recommendations already selected for \
this user by a separate, validated process (hard eligibility filtering, \
degree-progress-driven grouping, then per-group scoring and selection) — \
present the picks, not invent new ones.

The result is organised into GROUPS, each tied to one specific degree \
requirement (mandatory core, core course choice, an elective Vertical, or \
the Capstone path), each stating how many courses to pick from it. A group \
usually lists MORE courses than are actually required — each course is \
flagged `recommended: true` (a top pick that satisfies the requirement) or \
`recommended: false` (a good alternative the student can browse instead of \
the top pick(s)). A group can also have `required_pick_count: 0` — every \
course in it is then a non-binding, optional exploration option, not \
something the student needs to pick at all (its `note` explains why, e.g. \
another Vertical group already covers the actual remaining requirement).

Hard rules:
- Reproduce every group's label, required pick count, and each course's \
code/title/unit count EXACTLY as given below — never invent, drop, \
substitute, or re-rank a course, and never merge two groups into one.
- Clearly distinguish `recommended: true` picks from `recommended: false` \
alternatives when you present them — never present an alternative as if it \
were already the chosen course, and never present a required_pick_count: 0 \
group's courses as if the student must pick from them.
- Present the reasons/matched-skills/cautions for each course as evidence \
from that already-completed selection process, not as your own new judgement.
- If a group has no recommendations and carries a note, explain that \
honestly (e.g. no eligible candidate currently exists for that group) rather \
than omitting the group or inventing a course for it.
- If NOTES below flag a limitation (e.g. no target role matched, a course \
code wasn't recognised, a filter isn't supported), work it into the reply \
honestly — do not omit it or smooth it over.
- This is a course selection aid, not a graduation-requirement guarantee — \
frame it as such if the user's message implies otherwise."""


def _preclusion_display_text(row: dict) -> str:
    """knowledge.courses no longer carries NUSMods' raw preclusion prose —
    only the parsed, grad-relevant course-code array. Empty when the
    course has no preclusion applicable to a Graduate Coursework student."""
    codes = row.get("preclusion_codes")
    if not codes:
        return ""
    return "Must not have completed: " + ", ".join(codes)


def _offered_terms(row: dict) -> list[str]:
    """Renders current_ay_semesters (this AY's real NUSMods schedule) into
    display strings — empty when the course isn't scheduled this AY at
    all (still part of the programme, just not offered right now)."""
    ay = row.get("current_ay_label") or ""
    semesters = row.get("current_ay_semesters") or []
    return [f"Semester {n} ({ay})" if ay else f"Semester {n}" for n in semesters]


def _map_course(
    row: dict, module_skills: dict[str, list[str]], course_electives: dict[str, list[str]]
) -> dict:
    return {
        "code": row["course_code"],
        "title": (row.get("title") or "")[:300],
        "units": int(row["module_credit"]) if row.get("module_credit") is not None else 0,
        "section": (row.get("annex_section") or "")[:300],
        "skills": module_skills.get(row["course_code"], []),
        "can_recommend": bool(row.get("can_recommend")),
        "description": (row.get("description") or "")[:5000],
        # Grad-Coursework-only text: never carries an undergraduate-only
        # condition that doesn't apply to a DFT student (see module docstring).
        "prerequisite_text": (row.get("prerequisite_grad_text") or "")[:3000],
        "corequisite_text": (row.get("corequisite_grad_text") or "")[:3000],
        "preclusion_text": _preclusion_display_text(row),
        "offered_terms": _offered_terms(row),
        "course_time": None,
        "source_url": (row.get("source_url") or "")[:2048],
        "workload": list(row["workload"]) if row.get("workload") is not None else None,
        "data_quality": "needs_review" if row.get("needs_review") else "clean",
        "vertical": course_electives.get(row["course_code"], []),
    }


def _map_rule(chunk: dict) -> dict:
    md = chunk.get("metadata") or {}
    text = chunk.get("content") or chunk.get("context") or ""
    return {
        "rule_key": (chunk["chunk_key"] or "")[:300],
        "category": (md.get("category") or "curriculum")[:100],
        "intake": (md.get("intake") or "")[:100],
        "text": text[:5000] or "(no rule text available)",
    }


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    profile = get_profile(state.user_id) if state.user_id else None
    profile = profile or {}

    target_role = state.target_role_hint or profile.get("target_role_std") or profile.get("target_role_raw")

    role_profile = resolve_role_profile(target_role) if target_role else None
    if target_role and role_profile is None:
        # The report requires target_role and role_profile to be both
        # present or both absent — if resolution fails, drop target_role
        # too so the request stays valid rather than failing outright.
        target_role = None

    curated_role_courses: list[str] = []
    if role_profile is not None:
        curated_role_courses = [
            row["course_code"] for row in list_career_role_modules(role_profile["role_id"])
        ]

    module_skills = list_module_skills()
    course_electives = list_course_electives()
    request = {
        "goals": {
            "target_role": target_role,
            "target_industry": profile.get("target_industry_std") or profile.get("target_industry_raw"),
        },
        "background": {
            "academic_background": profile.get("academic_background_std") or profile.get("academic_background_raw"),
            "tech_level": profile.get("tech_level_std") or profile.get("tech_level_raw"),
            "school_tier": profile.get("school_tier"),
            "work_years": profile.get("work_years"),
            "completed_courses": [c[:300] for c in (profile.get("completed_courses") or [])][:50],
        },
        "role_profile": role_profile,
        "curated_role_courses": curated_role_courses,
        "course_catalog": [
            _map_course(row, module_skills, course_electives) for row in list_courses()
        ],
        "curriculum_rules": [_map_rule(chunk) for chunk in list_curriculum_rules()],
        "evidence_sources": [
            "applicant profile", "knowledge base course catalog", "knowledge base curriculum rules",
        ],
    }

    result = recommend_courses(request)
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(result, user_message, COURSE_RECOMMENDATION_STYLE_PROMPT, on_event=on_event)
    return ToolAnswer(text=answer, sources=sources, agent_used="course_recommendation_agent")


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text=_FALLBACK_REPLY, agent_used="course_recommendation_agent_fallback")


COURSE_RECOMMENDATION_TOOL = Tool(
    name="course_recommendation",
    description="Personalised course recommendations from the applicant's profile and the current curriculum.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"course_recommendation"}),
)
