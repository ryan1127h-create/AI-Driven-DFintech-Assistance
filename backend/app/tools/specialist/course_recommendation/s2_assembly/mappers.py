"""
S2 — maps knowledge-base rows into the report's course and rule items.

A course's `skills` are the union of the required_skills of the role tags
it carries (knowledge.course_tags -> tags_definition) — the same skill
vocabulary a role profile's required_skills use, so matching stays
like-for-like. `vertical` comes from knowledge.course_electives, and
`can_recommend`/`needs_review` from the catalogue (active course / a
description flagged for review). `prerequisite_text`/`preclusion_text`
are the grad-student-only, already-cleaned requirements rather than
NUSMods' raw text, which mixes in undergraduate-only conditions that never
apply to a DFT (Graduate Coursework) student.
"""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s2_assembly.prerequisites import parse as parse_requirements


def course_skills(course_tags: dict[str, list[str]], role_tags: list[dict]) -> dict[str, list[str]]:
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


def map_course(
    row: dict,
    course_skills: dict[str, list[str]],
    course_electives: dict[str, list[str]],
    course_tags: dict[str, list[str]],
    role_names: dict[str, str],
    schedule: dict[str, list[dict]] | None = None,
) -> dict:
    prerequisite = row.get("prerequisite_grad_text") or ""
    corequisite = row.get("corequisite_grad_text") or ""
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
        "role_tags": [
            {"tag": tag, "name": role_names.get(tag, tag)} for tag in course_tags.get(row["course_code"], [])
        ],
        "sessions": (schedule or {}).get(row["course_code"], []),
        "prerequisites": parse_requirements(prerequisite, corequisite),
    }


def map_rule(chunk: dict) -> dict:
    md = chunk.get("metadata") or {}
    text = chunk.get("content") or chunk.get("context") or ""
    return {
        "rule_key": (chunk["chunk_key"] or "")[:300],
        "category": (md.get("category") or "curriculum")[:100],
        "intake": (md.get("intake") or "")[:100],
        "text": text[:5000] or "(no rule text available)",
    }
