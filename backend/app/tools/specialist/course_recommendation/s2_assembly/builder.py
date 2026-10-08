"""
S2 — assembles the complete report the course_recommendation domain
consumes from what prefetch.py gathered: the user's profile facts, the
resolved role profile, and the knowledge base's catalogue (each course with
its role tags) and current-intake curriculum rules.

Pure function: no profile or knowledge-base access (everything arrives in
Prefetched). Current courses count as completed: the plan is for the semesters after
them. `preferences` (workload/style text) is not populated yet: nothing
upstream extracts it from the chat turn, so the domain runs with its safe
"no preference signal" default.
"""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s2_assembly.mappers import (
    course_skills,
    map_course,
    map_rule,
)
from app.tools.specialist.course_recommendation.s2_assembly.prefetched import LEVEL_FIELDS, Prefetched

_MAX_TEXT = 300  # the report's LongText limit


def other_roles_note(prefetched: Prefetched) -> str | None:
    """A note naming the profile's other target roles, when the plan was
    built around one of several."""
    role_tag = prefetched.role_tag
    other_roles = [t for t in prefetched.facts.get("target_role_families") or [] if t != role_tag]
    if not (role_tag and other_roles):
        return None
    return (
        "Planned around the main target role; the profile also lists: "
        + ", ".join(prefetched.role_labels[t] for t in other_roles) + "."
    )


def _academic_background(labels: dict[str, str]) -> str | None:
    parts = []
    if "degree_discipline_category" in labels:
        parts.append(labels["degree_discipline_category"])
    if "prior_coursework" in labels:
        parts.append("prior coursework: " + labels["prior_coursework"])
    return "; ".join(parts)[:_MAX_TEXT] or None


def _tech_level(labels: dict[str, str], readiness_notes: tuple[str, ...]) -> str | None:
    parts = [f"{name}: {labels[key]}" for key, name in LEVEL_FIELDS if key in labels]
    if "tech_stack" in labels:
        parts.append("tech stack: " + labels["tech_stack"])
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


def build_request(prefetched: Prefetched) -> dict:
    """The complete report course_recommendation consumes. Derived
    readiness gaps extend the stated tech level."""
    role_profile = prefetched.role_profile
    # The report requires target_role and role_profile to be both present
    # or both absent.
    target_role = role_profile["role_title"] if role_profile else None

    skills = course_skills(prefetched.course_tags, prefetched.role_tags)
    role_names = {row["tag"]: row["name_en"] for row in prefetched.role_tags}
    return {
        "goals": {
            "target_role": target_role,
            "target_industry": None,
        },
        "background": {
            "academic_background": _academic_background(prefetched.fact_labels),
            "tech_level": _tech_level(prefetched.fact_labels, prefetched.readiness_notes),
            "school_tier": None,
            "work_years": None,
            "completed_courses": _done_course_codes(prefetched.facts),
        },
        "role_profile": role_profile,
        "course_catalog": [
            map_course(row, skills, prefetched.course_electives, prefetched.course_tags, role_names)
            for row in prefetched.courses
        ],
        "curriculum_rules": [map_rule(chunk) for chunk in prefetched.curriculum_rules],
        "evidence_sources": [
            "user profile", "knowledge base course catalog", "knowledge base curriculum rules",
        ],
    }
