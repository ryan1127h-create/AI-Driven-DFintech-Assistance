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

Roles are the knowledge base's 12 role tags. A course's `skills` are the
union of the required_skills of the role tags it carries
(knowledge.course_tags -> tags_definition) — the same skill vocabulary a
role profile's required_skills use, so matching stays like-for-like.
`vertical` comes from knowledge.course_electives, and
`can_recommend`/`needs_review` from the catalogue (active course / a
description flagged for review). `prerequisite_text`/`preclusion_text`
are the grad-student-only, already-cleaned requirements rather than
NUSMods' raw text, which mixes in undergraduate-only conditions that never
apply to a DFT (Graduate Coursework) student; there is no corequisite
data.

The courses tagged with the target role are passed as
`curated_role_courses` — a soft scoring bonus in the domain's STAGE 5,
never a restriction.

Profile facts come from the profile's "course" purpose (consent-filtered;
empty without consent, in which case the recommendation is simply not
personalised). The target role is the role the user names in the message
if it maps to a role tag, else the profile's main_target_role, else the
first of its target_role_families; other listed roles are mentioned in the
result's notes. Current courses count as completed: the plan is for the
semesters after them. `preferences` (workload/style text) is not populated
here yet: nothing upstream of this tool currently extracts that from the
chat turn, so the domain runs with its safe "no preference signal" default.
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.interface import (
    get_role_profile,
    list_course_electives,
    list_course_tags,
    list_courses,
    list_curriculum_rules,
    list_role_tags,
    match_role_tag,
)
from app.domains.profile.interface import derived_course_notes, describe_value, get_profile_for_purpose
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


# The contract caps the curated shortlist.
_MAX_CURATED_COURSES = 20


def _course_skills(course_tags: dict[str, list[str]], role_tags: list[dict]) -> dict[str, list[str]]:
    """course_code -> the union of its role tags' required_skills, in a
    stable order."""
    skills_by_tag = {row["tag"]: row["required_skills"] for row in role_tags}
    result: dict[str, list[str]] = {}
    for code, tags in course_tags.items():
        skills: list[str] = []
        for tag in tags:
            for skill in skills_by_tag.get(tag, []):
                if skill not in skills:
                    skills.append(skill)
        result[code] = skills
    return result


def _preclusion_display_text(row: dict) -> str:
    """The catalogue carries preclusions as a parsed, grad-relevant
    course-code array. Empty when the course has no preclusion applicable
    to a Graduate Coursework student."""
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
    row: dict, course_skills: dict[str, list[str]], course_electives: dict[str, list[str]]
) -> dict:
    return {
        "code": row["course_code"],
        "title": (row.get("title") or "")[:300],
        "units": int(row["module_credit"]) if row.get("module_credit") is not None else 0,
        "section": (row.get("annex_section") or "")[:300],
        "skills": course_skills.get(row["course_code"], []),
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


# Skill-level fields rendered into the report's tech_level text.
_LEVEL_FIELDS = (
    ("code_level", "Programming"),
    ("ml_ai_level", "Machine learning"),
    ("math_stats_level", "Maths & statistics"),
    ("finance_level", "Finance"),
    ("data_engineering_level", "Data engineering"),
    ("blockchain_level", "Blockchain"),
)
_MAX_TEXT = 300  # the report's LongText limit


def _resolve_role_tag(facts: dict, target_role_hint: str | None) -> str | None:
    """The role named in the message (if it is a known role tag), else the
    profile's main role, else its first listed role."""
    if target_role_hint:
        tag = match_role_tag(target_role_hint)
        if tag:
            return tag
    families = facts.get("target_role_families") or []
    return facts.get("main_target_role") or (families[0] if families else None)


def _academic_background(facts: dict) -> str | None:
    parts = []
    if "degree_discipline_category" in facts:
        parts.append(describe_value("degree_discipline_category", facts["degree_discipline_category"]))
    if "prior_coursework" in facts:
        parts.append("prior coursework: " + describe_value("prior_coursework", facts["prior_coursework"]))
    return "; ".join(parts)[:_MAX_TEXT] or None


def _tech_level(facts: dict, readiness_notes: list[str]) -> str | None:
    parts = [
        f"{name}: {describe_value(key, facts[key])}"
        for key, name in _LEVEL_FIELDS if key in facts
    ]
    if "tech_stack" in facts:
        parts.append("tech stack: " + describe_value("tech_stack", facts["tech_stack"]))
    parts.extend(readiness_notes)
    return "; ".join(parts)[:_MAX_TEXT] or None


def _done_course_codes(facts: dict) -> list[str]:
    """Completed plus current courses, by code."""
    codes: list[str] = []
    for key in ("completed_modules", "current_modules"):
        for item in facts.get(key) or []:
            code = item.get("course_code") if isinstance(item, dict) else item
            if code and code not in codes:
                codes.append(code)
    return codes[:50]


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    facts = get_profile_for_purpose(state.user_id, "course") if state.user_id else {}
    role_tag = _resolve_role_tag(facts, state.target_role_hint)
    derived = derived_course_notes(state.user_id) if state.user_id else {"readiness": [], "graduation": []}

    result = recommend_courses(build_request(facts, role_tag, readiness_notes=derived["readiness"]))
    # Graduation risks aren't a recommendation input; they ride along so the
    # reply can point them out.
    result["notes"].extend(derived["graduation"])
    other_roles = [t for t in facts.get("target_role_families") or [] if t != role_tag]
    if role_tag and other_roles:
        result["notes"].append(
            "Planned around the main target role; the profile also lists: "
            + describe_value("target_role_families", other_roles) + "."
        )
    user_message = last_human_message(state.messages)
    answer, sources = render_structured_reply(
        result, user_message, COURSE_RECOMMENDATION_STYLE_PROMPT, on_event=on_event, depth=state.answer_depth,
    )
    return ToolAnswer(text=answer, sources=sources, agent_used="course_recommendation_agent")


def build_request(facts: dict, role_tag: str | None, readiness_notes: list[str] | None = None) -> dict:
    """The complete report course_recommendation consumes: the user's
    profile facts (purpose "course"), the resolved role tag, and the
    knowledge base's catalogue and current-intake curriculum rules.
    readiness_notes (derived readiness gaps) extend the stated tech level."""
    role_profile = get_role_profile(role_tag) if role_tag else None
    # The report requires target_role and role_profile to be both present
    # or both absent.
    target_role = role_profile["role_title"] if role_profile else None

    course_tags = list_course_tags()
    curated_role_courses: list[str] = []
    if role_profile is not None:
        curated_role_courses = sorted(
            code for code, tags in course_tags.items() if role_profile["role_id"] in tags
        )[:_MAX_CURATED_COURSES]

    course_skills = _course_skills(course_tags, list_role_tags())
    course_electives = list_course_electives()
    return {
        "goals": {
            "target_role": target_role,
            "target_industry": None,
        },
        "background": {
            "academic_background": _academic_background(facts),
            "tech_level": _tech_level(facts, readiness_notes or []),
            "school_tier": None,
            "work_years": None,
            "completed_courses": _done_course_codes(facts),
        },
        "role_profile": role_profile,
        "curated_role_courses": curated_role_courses,
        "course_catalog": [
            _map_course(row, course_skills, course_electives) for row in list_courses()
        ],
        "curriculum_rules": [_map_rule(chunk) for chunk in list_curriculum_rules()],
        "evidence_sources": [
            "user profile", "knowledge base course catalog", "knowledge base curriculum rules",
        ],
    }


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
