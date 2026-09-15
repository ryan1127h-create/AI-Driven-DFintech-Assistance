"""
STAGE 3 — degree progress computation. Turns "which courses has this
student completed" into the numeric ground truth every later stage reads
instead of re-deriving quota state itself: how many of the 4 mandatory
core courses are done, how many of the 11-choose-3 core electives, how
many elective units, how many of those sit at the 4000 level, and where
the student stands on the Capstone-vs-three-more-electives decision.

Pure function, no I/O. Depends only on pipeline/curriculum_structure.py's
constants and the Course facts STAGE 2 already classified.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import (
    CapstonePath,
    Course,
    DegreeProgress,
)
from app.domains.specialist.course_recommendation.pipeline import curriculum_structure as cs

# rule:cur_replacement_policy names these two specifically — BMD5302 and
# IT5006 have no approved-replacement path.
_REPLACEABLE_MANDATORY = frozenset({"BMD5301", "IT5001X"})


def compute(
    courses: list[Course],
    completed_recognized: tuple[str, ...],
    completed_units: int,
) -> DegreeProgress:
    by_code = {c.code: c for c in courses}
    completed_set = set(completed_recognized)

    core_mandatory_done = tuple(sorted(cs.CORE_MANDATORY & completed_set))
    core_mandatory_remaining = tuple(sorted(cs.CORE_MANDATORY - completed_set))

    completed_choice = sorted(cs.CORE_CHOICE_POOL & completed_set)
    core_choice_done = tuple(completed_choice[: cs.CORE_CHOICE_REQUIRED_COUNT])
    core_choice_surplus = tuple(completed_choice[cs.CORE_CHOICE_REQUIRED_COUNT :])
    core_choice_remaining_count = max(
        0, cs.CORE_CHOICE_REQUIRED_COUNT - len(completed_choice)
    )

    outstanding_replaceable = _REPLACEABLE_MANDATORY & set(core_mandatory_remaining)
    core_replacement_cautions = tuple(
        f"{code} completed — may be usable as an approved replacement for "
        f"{'/'.join(sorted(outstanding_replaceable))} pending School of Computing "
        "approval; not counted toward the mandatory requirement automatically."
        for code in sorted(cs.CORE_MANDATORY_REPLACEMENTS & completed_set)
        if outstanding_replaceable
    )

    elective_units_done = sum(
        by_code[code].units
        for code in completed_recognized
        if code in by_code and by_code[code].requirement_role == "elective"
    )
    # rule:cur_elective_rules — FT50xx completed beyond the 3-course core
    # choice quota counts toward elective units.
    elective_units_done += sum(by_code[code].units for code in core_choice_surplus if code in by_code)

    elective_level4000_used = sum(
        1
        for code in completed_recognized
        if code in by_code
        and by_code[code].requirement_role == "elective"
        and by_code[code].level == cs.MIN_COUNTABLE_ELECTIVE_LEVEL
    )
    elective_level4000_cap_reached = elective_level4000_used >= cs.MAX_LEVEL_4000_ELECTIVES

    alternative_target = cs.ELECTIVE_UNITS_BASE + (
        cs.CAPSTONE_ALTERNATIVE_ELECTIVE_COUNT * cs.TYPICAL_ELECTIVE_UNITS
    )
    core_fully_done = not core_mandatory_remaining and core_choice_remaining_count == 0
    capstone_done = cs.CAPSTONE_CODE in completed_set

    capstone_path: CapstonePath
    if capstone_done:
        capstone_path = "direct_completed"
        elective_units_target = cs.ELECTIVE_UNITS_BASE
    elif elective_units_done >= alternative_target:
        # Structurally satisfied both the base 12 and the 3-more-elective
        # alternative without ever completing FT5007 — read as "took the
        # elective-alternative path". This is a heuristic (the student's
        # actual capstone intent isn't captured anywhere upstream), not a
        # database fact — see this module's caveat in the workflow notes.
        capstone_path = "elective_alternative_complete"
        elective_units_target = alternative_target
    elif core_fully_done and elective_units_done >= cs.ELECTIVE_UNITS_BASE:
        capstone_path = "direct_in_progress"
        elective_units_target = cs.ELECTIVE_UNITS_BASE
    elif elective_units_done > cs.ELECTIVE_UNITS_BASE:
        capstone_path = "elective_alternative_in_progress"
        elective_units_target = alternative_target
    else:
        capstone_path = "undecided"
        elective_units_target = cs.ELECTIVE_UNITS_BASE

    return DegreeProgress(
        core_mandatory_done=core_mandatory_done,
        core_mandatory_remaining=core_mandatory_remaining,
        core_choice_done=core_choice_done,
        core_choice_remaining_count=core_choice_remaining_count,
        core_choice_surplus=core_choice_surplus,
        core_replacement_cautions=core_replacement_cautions,
        capstone_path=capstone_path,
        elective_units_done=elective_units_done,
        elective_units_target=elective_units_target,
        elective_level4000_used=elective_level4000_used,
        elective_level4000_cap_reached=elective_level4000_cap_reached,
        total_units_done=completed_units,
        total_units_target=cs.TOTAL_PROGRAMME_UNITS,
    )
