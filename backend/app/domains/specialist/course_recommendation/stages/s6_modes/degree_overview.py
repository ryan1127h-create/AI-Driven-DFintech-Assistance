"""
S6 mode "degree_overview" — one group per open requirement slot (mandatory
core, core choice, each Vertical, the Capstone path), each listing its
recommendation(s) first and a few browsable alternatives after.

Pure function, no I/O.
"""

from __future__ import annotations

from typing import Sequence

from app.domains.specialist.course_recommendation.models import (
    CandidatePool,
    Group,
    Pick,
    Recommendation,
    SlotPicks,
)

SECONDARY_VERTICAL_NOTE = (
    "This Vertical isn't currently the primary source for your remaining "
    "elective requirement (see the other Vertical group for that) — these "
    "are optional courses worth exploring if this direction interests you."
)


def _recommendation(pick: Pick, pool: CandidatePool, *, recommended: bool) -> Recommendation:
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
    }


def _group(entry: SlotPicks, pool: CandidatePool) -> Group:
    slot = entry.slot
    note = entry.note
    if slot.slot_type == "elective" and slot.required_pick_count == 0 and entry.picks:
        note = f"{note} {SECONDARY_VERTICAL_NOTE}" if note else SECONDARY_VERTICAL_NOTE
    return {
        "slot_id": slot.slot_id,
        "slot_type": slot.slot_type,
        "label": slot.label,
        "required_pick_count": slot.required_pick_count,
        "recommendations": [
            _recommendation(pick, pool, recommended=index < slot.required_pick_count)
            for index, pick in enumerate(entry.picks)
        ],
        "note": note,
    }


class DegreeOverview:
    def assemble(self, slot_picks: Sequence[SlotPicks], pool: CandidatePool) -> list[Group]:
        return [_group(entry, pool) for entry in slot_picks]
