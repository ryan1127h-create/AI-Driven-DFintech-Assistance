"""
S2 — assembles the complete report the course_recommendation domain
consumes from what prefetch.py gathered and what S1 read from the message:
the user's profile facts, the resolved role profile, what this request
asks for, and the knowledge base's catalogue (each course with its role
tags) and current-intake curriculum rules.

Pure function: no profile or knowledge-base access (everything arrives in
Prefetched and ParsedRequest). Current courses count as completed: the
plan is for the semesters after them. What the message states wins over
the profile for this request (e.g. a Capstone intent said in passing).
"""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
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


def _student(facts: dict, parsed: ParsedRequest) -> dict:
    tracks = ("computing_technologies", "financial_data_analytics_intelligence", "digital_financial_transactions_risk")
    interest = [t for t in facts.get("track_interest") or [] if t in tracks]
    chosen = facts.get("track_chosen")
    intent = parsed.capstone_intent or facts.get("capstone_intent")
    return {
        "capstone_intent": intent if intent in ("capstone_research", "capstone_internship", "electives_instead") else None,
        "track_interest": interest,
        "track_chosen": chosen if chosen in tracks else None,
    }


def _constraints(parsed: ParsedRequest) -> dict:
    return {
        "include_codes": parsed.include_codes,
        "exclude_codes": parsed.exclude_codes,
        "preferred_skills": parsed.preferred_skills,
        "keywords": parsed.keywords,
        "vertical_preference": parsed.vertical_preference,
        "workload_style": parsed.workload_style,
    }


def build_request(prefetched: Prefetched, parsed: ParsedRequest | None = None) -> dict:
    """The complete report course_recommendation consumes. Derived
    readiness gaps extend the stated tech level. Without a parsed request
    the report asks for the overall recommendation, with no constraints."""
    parsed = parsed or ParsedRequest()
    role_profile = prefetched.role_profile
    # The report requires target_role and role_profile to be both present
    # or both absent.
    target_role = role_profile["role_title"] if role_profile else None

    skills = course_skills(prefetched.course_tags, prefetched.role_tags)
    role_names = {row["tag"]: row["name_en"] for row in prefetched.role_tags}
    return {
        "mode": parsed.mode,
        "goals": {"target_role": target_role},
        "background": {
            "academic_background": _academic_background(prefetched.fact_labels),
            "tech_level": _tech_level(prefetched.fact_labels, prefetched.readiness_notes),
            "completed_courses": _done_course_codes(prefetched.facts),
        },
        "student": _student(prefetched.facts, parsed),
        "constraints": _constraints(parsed),
        "role_profile": role_profile,
        "course_catalog": [
            map_course(
                row, skills, prefetched.course_electives, prefetched.course_tags, role_names,
                prefetched.course_schedule,
            )
            for row in prefetched.courses
        ],
        "curriculum_rules": [map_rule(chunk) for chunk in prefetched.curriculum_rules],
        "evidence_sources": [
            "user profile", "knowledge base course catalog", "knowledge base curriculum rules",
        ],
    }
