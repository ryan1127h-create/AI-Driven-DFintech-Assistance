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

from datetime import date

from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.specialist.course_recommendation.s2_assembly.mappers import (
    course_skills,
    map_course,
    map_rule,
)
from app.tools.specialist.course_recommendation.s2_assembly import terms
from app.tools.specialist.course_recommendation.s2_assembly.prefetched import LEVEL_FIELDS, Prefetched

_MAX_TEXT = 300  # the report's LongText limit


def other_roles_note(prefetched: Prefetched) -> str | None:
    """A note naming the profile's other target roles, when the plan was
    built around one of several."""
    role_tag = prefetched.role_tag
    other_roles = [t for t in prefetched.facts.get("target_role_families") or [] if t != role_tag]
    if not (role_tag and other_roles):
        return None
    basis = "the role named in the message" if prefetched.stated_role_tag else "the main target role"
    return (
        f"Planned around {basis}; the profile also lists: "
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


_TAKEN_KEYS = (("completed", "completed_modules"), ("in_progress", "current_modules"), ("planned", "planned_modules"))


def progress_basis(facts: dict) -> dict[str, list[str]]:
    """The course codes degree progress is counted from, by status: none of
    them is recommended again, but only the completed ones are finished —
    the reply says which is which."""
    basis: dict[str, list[str]] = {}
    for status, key in _TAKEN_KEYS:
        codes = [item.get("course_code") if isinstance(item, dict) else item for item in facts.get(key) or []]
        basis[status] = [c for c in codes if c]
    return basis


def _done_course_codes(facts: dict, with_planned: bool = True) -> list[str]:
    """Completed and current courses, by code, plus the planned ones unless
    `with_planned` is off (a semester plan places them itself)."""
    codes: list[str] = []
    for status, status_codes in progress_basis(facts).items():
        if status == "planned" and not with_planned:
            continue
        for code in status_codes:
            if code not in codes:
                codes.append(code)
    return codes[:50]


def _student(facts: dict, parsed: ParsedRequest) -> dict:
    tracks = ("computing_technologies", "financial_data_analytics_intelligence", "digital_financial_transactions_risk")
    interest = [t for t in facts.get("track_interest") or [] if t in tracks]
    chosen = facts.get("track_chosen")
    intent = parsed.capstone_intent or facts.get("capstone_intent")
    study_mode = parsed.study_mode or facts.get("study_mode")
    return {
        "study_mode": study_mode if study_mode in ("full_time", "part_time", "undecided") else None,
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
        "avoid_time_windows": parsed.avoid_time_windows,
        "avoid_days": parsed.avoid_days,
    }


def _planning(parsed: ParsedRequest, today: date) -> dict | None:
    """For a semester plan: the semester asked about (the next one unless
    named) and the units asked for."""
    if parsed.mode != "semester_plan":
        return None
    term = terms.resolve(parsed.target_semester, today)
    return {
        "ay": term.schedule_ay,
        "semester": term.semester,
        "label": term.label,
        "requested_units": parsed.unit_cap,
    }


def build_request(prefetched: Prefetched, parsed: ParsedRequest | None = None, today: date | None = None) -> dict:
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
        "planning": _planning(parsed, today or date.today()),
        "goals": {"target_role": target_role},
        "background": {
            "academic_background": _academic_background(prefetched.fact_labels),
            "tech_level": _tech_level(prefetched.fact_labels, prefetched.readiness_notes),
            "completed_courses": _done_course_codes(prefetched.facts, with_planned=parsed.mode != "semester_plan"),
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
