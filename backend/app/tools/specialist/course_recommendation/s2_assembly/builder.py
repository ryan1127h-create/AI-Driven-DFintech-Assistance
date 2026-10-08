"""
S2 — assembles the complete report the course_recommendation domain
consumes: the user's profile facts (purpose "course"), the resolved role
profile and its curated course shortlist, and the knowledge base's
catalogue and current-intake curriculum rules.

The target role is the role the user names in the message if it maps to a
role tag, else the profile's main_target_role, else the first of its
target_role_families. The courses tagged with that role are passed as
`curated_role_courses` — a soft scoring bonus, never a restriction.
Current courses count as completed: the plan is for the semesters after
them. `preferences` (workload/style text) is not populated yet: nothing
upstream extracts it from the chat turn, so the domain runs with its safe
"no preference signal" default.
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
from app.domains.profile.interface import describe_value
from app.tools.specialist.course_recommendation.s2_assembly.mappers import (
    course_skills,
    map_course,
    map_rule,
)

# The contract caps the curated shortlist.
_MAX_CURATED_COURSES = 20

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


def resolve_role_tag(facts: dict, target_role_hint: str | None) -> str | None:
    """The role named in the message (if it is a known role tag), else the
    profile's main role, else its first listed role."""
    if target_role_hint:
        tag = match_role_tag(target_role_hint)
        if tag:
            return tag
    families = facts.get("target_role_families") or []
    return facts.get("main_target_role") or (families[0] if families else None)


def other_roles_note(facts: dict, role_tag: str | None) -> str | None:
    """A note naming the profile's other target roles, when the plan was
    built around one of several."""
    other_roles = [t for t in facts.get("target_role_families") or [] if t != role_tag]
    if not (role_tag and other_roles):
        return None
    return (
        "Planned around the main target role; the profile also lists: "
        + describe_value("target_role_families", other_roles) + "."
    )


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


def build_request(facts: dict, role_tag: str | None, readiness_notes: list[str] | None = None) -> dict:
    """The complete report course_recommendation consumes. readiness_notes
    (derived readiness gaps) extend the stated tech level."""
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

    skills = course_skills(course_tags, list_role_tags())
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
            map_course(row, skills, course_electives) for row in list_courses()
        ],
        "curriculum_rules": [map_rule(chunk) for chunk in list_curriculum_rules()],
        "evidence_sources": [
            "user profile", "knowledge base course catalog", "knowledge base curriculum rules",
        ],
    }
