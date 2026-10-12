"""
S6 — one picked course as it's returned, shared by every mode: catalogue
facts, the selection's reason, synopsis and evidence, cautions, and the
score breakdown for audit.

Pure function, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import CandidatePool, Pick, Recommendation


def build(pick: Pick, pool: CandidatePool, *, recommended: bool, counts_toward: str | None = None) -> Recommendation:
    course = pick.scored.course
    cautions: list[str] = []
    if course.code in pool.prerequisite_cautions:
        cautions.append(
            f"Prerequisite not yet confirmed among completed courses: {course.prerequisite_text}"
        )
    if course.corequisite_text:
        cautions.append(f"Corequisite: {course.corequisite_text}")
    if pick.scored.workload_note:
        cautions.append(pick.scored.workload_note)

    return {
        "course_code": course.code,
        "course_title": course.title,
        "units": course.units,
        "section": course.section,
        "vertical": list(course.vertical),
        "level": course.level,
        "offered_terms": list(course.offered_terms),
        "course_time": course.course_time,
        "workload": list(course.workload) if course.workload is not None else None,
        "matched_skills": pick.scored.matched_skills,
        "reason": pick.reason,
        "recommended": recommended,
        "caution": " | ".join(cautions) or None,
        "score_breakdown": [
            {"signal": item.signal, "delta": item.delta, "evidence": item.evidence}
            for item in pick.scored.breakdown
        ],
        "synopsis": pick.synopsis,
        "evidence": list(pick.evidence),
        "counts_toward": counts_toward,
    }
