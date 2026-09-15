"""
STAGE 4 — requirement slot derivation and cross-slot conflict resolution.

Turns DegreeProgress's numeric state into the actual "Group A / Group B /
Group C" skeleton: one open slot per still-unmet requirement category,
each carrying how many picks it needs and which eligible courses could
fill it. A slot for a fully-satisfied requirement is never created — an
advanced student simply sees fewer, different slots than a fresh one.

Every slot shows more candidates than it strictly requires (`display_count`
= `required_pick_count` + EXTRA_DISPLAY_OPTIONS, capped by how many
eligible candidates exist) so STAGE 5 hands the student real choice
instead of one pre-made decision.

Vertical electives share ONE quota, not one each: the programme only
requires the total elective units to be met, however they are split
across the 3 Verticals — showing three independent "pick N" groups would
overstate the real remaining need three-fold. Only the Vertical that best
covers the student's skill gaps carries the real `required_pick_count`
("primary"); the other Verticals with eligible candidates still get a
slot (so the student can see every track), but with required_pick_count=0
— every course shown there is an optional, non-binding alternative.

Cross-slot conflict resolution: if a course sits in more than one slot's
candidate list (not currently triggered by any code in the catalogue —
see catalog.py's classification-order note — but kept as a defensive
guard against a future data change, e.g. a course tagged into two
verticals), it is kept only in the highest-priority slot
(core_mandatory > core_choice > elective/capstone) so it is never
suggested twice as if it were two independent opportunities.

Pure function, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import replace

from app.domains.specialist.course_recommendation.models import (
    CandidatePool,
    Course,
    DegreeProgress,
    RequirementSlot,
)
from app.domains.specialist.course_recommendation.pipeline import curriculum_structure as cs

_SLOT_PRIORITY = {"core_mandatory": 0, "core_choice": 1, "elective": 2, "capstone": 2}

# How many more candidates to show beyond what's strictly required, so the
# student gets real choice instead of one pre-made decision (confirmed
# design: fixed +2, capped by how many eligible candidates actually exist).
EXTRA_DISPLAY_OPTIONS = 2

# Vertical labels are long (e.g. "Vertical #3. Digital Financial
# Transactions and Risk Management") — a short display label per slot
# keeps the final response readable without losing the full name (still
# available via each recommendation's own `vertical` field).
_VERTICAL_SHORT_LABEL = {
    "Vertical #1. Computing Technologies": "Vertical #1 · Computing Technologies",
    "Vertical #2. Financial Data Analytics and Intelligence": "Vertical #2 · Financial Data Analytics",
    "Vertical #3. Digital Financial Transactions and Risk Management": "Vertical #3 · Digital Financial Transactions",
}

SECONDARY_VERTICAL_NOTE = (
    "This Vertical isn't currently the primary source for your remaining "
    "elective requirement (see the other Vertical group for that) — these "
    "are optional courses worth exploring if this direction interests you."
)


def _remaining_course_count(remaining_units: int) -> int:
    if remaining_units <= 0:
        return 0
    return max(1, math.ceil(remaining_units / cs.TYPICAL_ELECTIVE_UNITS))


def _display_count(required_pick_count: int, candidate_count: int) -> int:
    return min(required_pick_count + EXTRA_DISPLAY_OPTIONS, candidate_count)


def _make_slot(slot_id: str, slot_type, label: str, required_pick_count: int, candidates: tuple[str, ...]) -> RequirementSlot:
    return RequirementSlot(
        slot_id=slot_id,
        slot_type=slot_type,
        label=label,
        required_pick_count=required_pick_count,
        display_count=_display_count(required_pick_count, len(candidates)),
        eligible_candidates=candidates,
    )


def _primary_vertical(by_vertical: dict[str, list[str]], courses_by_code: dict[str, Course], skill_gaps: tuple[str, ...]) -> str:
    """Which Vertical best covers the student's skill gaps — a lightweight
    proxy available from STAGE 2/3 output alone (no full STAGE 5 scoring
    needed just to rank Verticals against each other). Ties break on more
    eligible candidates, then alphabetically for full determinism."""
    gap_set = set(skill_gaps)

    def _priority(vertical: str) -> tuple[int, int]:
        codes = by_vertical[vertical]
        covered = {s for code in codes for s in courses_by_code[code].skills if s in gap_set}
        return (len(covered), len(codes))

    return max(sorted(by_vertical), key=_priority)


def derive_slots(
    courses: list[Course],
    pool: CandidatePool,
    progress: DegreeProgress,
) -> tuple[RequirementSlot, ...]:
    by_code = {c.code: c for c in pool.eligible}
    slots: list[RequirementSlot] = []

    if progress.core_mandatory_remaining:
        candidates = tuple(code for code in progress.core_mandatory_remaining if code in by_code)
        if candidates:
            slots.append(
                _make_slot(
                    "core_mandatory", "core_mandatory", "Mandatory core courses",
                    min(2, len(candidates)), candidates,
                )
            )

    if progress.core_choice_remaining_count > 0:
        candidates = tuple(code for code in sorted(cs.CORE_CHOICE_POOL) if code in by_code)
        if candidates:
            slots.append(
                _make_slot(
                    "core_choice", "core_choice", "Core course choice (3 of 11 FT50xx)",
                    min(2, progress.core_choice_remaining_count, len(candidates)), candidates,
                )
            )

    # One slot per Vertical with eligible candidates — a presentation
    # choice (helps a student see each track), but only ONE of them
    # ("primary") carries the real required_pick_count; see module docstring.
    remaining_elective_units = max(0, progress.elective_units_target - progress.elective_units_done)
    if remaining_elective_units > 0:
        by_vertical: dict[str, list[str]] = {}
        for course in pool.eligible:
            if course.requirement_role != "elective":
                continue
            for vertical in course.vertical:
                by_vertical.setdefault(vertical, []).append(course.code)
        if by_vertical:
            pick_count = min(2, _remaining_course_count(remaining_elective_units))
            primary = _primary_vertical(by_vertical, by_code, pool.skill_gaps)
            for vertical in sorted(by_vertical):
                is_primary = vertical == primary
                candidates = tuple(by_vertical[vertical])
                slot = _make_slot(
                    f"elective::{vertical}", "elective",
                    _VERTICAL_SHORT_LABEL.get(vertical, f"Elective · {vertical}"),
                    pick_count if is_primary else 0,
                    candidates,
                )
                slots.append(slot)

    if progress.capstone_path in ("direct_in_progress", "elective_alternative_in_progress"):
        if cs.CAPSTONE_CODE in by_code:
            slots.append(
                _make_slot("capstone", "capstone", "Capstone path", 1, (cs.CAPSTONE_CODE,))
            )

    return _resolve_overlaps(slots)


def _resolve_overlaps(slots: list[RequirementSlot]) -> tuple[RequirementSlot, ...]:
    order = sorted(range(len(slots)), key=lambda i: _SLOT_PRIORITY[slots[i].slot_type])
    owner: dict[str, int] = {}
    for idx in order:
        for code in slots[idx].eligible_candidates:
            owner.setdefault(code, idx)

    resolved: list[RequirementSlot] = []
    for idx, slot in enumerate(slots):
        kept = tuple(code for code in slot.eligible_candidates if owner[code] == idx)
        if kept == slot.eligible_candidates:
            resolved.append(slot)
        else:
            resolved.append(
                replace(
                    slot,
                    eligible_candidates=kept,
                    display_count=_display_count(slot.required_pick_count, len(kept)),
                )
            )
    return tuple(resolved)
