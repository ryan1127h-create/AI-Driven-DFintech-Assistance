"""Exercises pipeline/degree_progress.py: STAGE 3's numeric ground truth.

Courses here are constructed already-classified (requirement_role/level
set directly) since this module consumes STAGE 2's output — it never
classifies anything itself.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course
from app.domains.specialist.course_recommendation.pipeline import curriculum_structure as cs
from app.domains.specialist.course_recommendation.pipeline import degree_progress


def _course(code: str, requirement_role: str, units: int = 4, level: int | None = 5000) -> Course:
    return Course(
        code=code,
        title=code,
        units=units,
        section="",
        skills=(),
        description="",
        prerequisite_text="",
        preclusion_text="",
        can_recommend=True,
        source_url="",
        requirement_role=requirement_role,  # type: ignore[arg-type]
        level=level,
    )


def _mandatory_and_choice_courses() -> list[Course]:
    return [_course(c, "core_mandatory") for c in cs.CORE_MANDATORY] + [
        _course(c, "core_choice") for c in sorted(cs.CORE_CHOICE_POOL)
    ]


def test_fresh_student_has_everything_remaining():
    progress = degree_progress.compute(_mandatory_and_choice_courses(), (), 0)
    assert set(progress.core_mandatory_remaining) == cs.CORE_MANDATORY
    assert progress.core_choice_remaining_count == cs.CORE_CHOICE_REQUIRED_COUNT
    assert progress.capstone_path == "undecided"
    assert progress.elective_units_done == 0
    assert progress.elective_units_target == cs.ELECTIVE_UNITS_BASE


def test_core_choice_surplus_counts_toward_electives():
    courses = _mandatory_and_choice_courses()
    completed_choice = sorted(cs.CORE_CHOICE_POOL)[:4]  # one more than required
    progress = degree_progress.compute(courses, tuple(completed_choice), sum(4 for _ in completed_choice))
    assert len(progress.core_choice_done) == cs.CORE_CHOICE_REQUIRED_COUNT
    assert len(progress.core_choice_surplus) == 1
    assert progress.elective_units_done == 4  # the surplus course's units


def test_replacement_caution_fires_only_while_target_mandatory_outstanding():
    courses = _mandatory_and_choice_courses() + [_course("IT5003", "elective")]
    progress = degree_progress.compute(courses, ("IT5003",), 4)
    assert any("IT5003" in note for note in progress.core_replacement_cautions)

    # Once BMD5301 and IT5001X are both done, the caution has nothing left to suggest.
    completed = ("IT5003", "BMD5301", "IT5001X")
    progress2 = degree_progress.compute(courses, completed, 12)
    assert progress2.core_replacement_cautions == ()


def test_capstone_direct_completed():
    courses = _mandatory_and_choice_courses() + [_course(cs.CAPSTONE_CODE, "capstone", units=12)]
    completed = tuple(cs.CORE_MANDATORY) + tuple(sorted(cs.CORE_CHOICE_POOL))[:3] + (cs.CAPSTONE_CODE,)
    progress = degree_progress.compute(courses, completed, 40)
    assert progress.capstone_path == "direct_completed"


def test_capstone_direct_in_progress_once_core_done_and_electives_met():
    electives = [_course(f"EL{i}", "elective", units=4) for i in range(3)]
    courses = _mandatory_and_choice_courses() + electives
    completed = tuple(cs.CORE_MANDATORY) + tuple(sorted(cs.CORE_CHOICE_POOL))[:3] + tuple(
        c.code for c in electives
    )
    progress = degree_progress.compute(courses, completed, 40)
    assert progress.capstone_path == "direct_in_progress"
    assert progress.elective_units_done == 12


def test_capstone_elective_alternative_complete_at_24_units():
    electives = [_course(f"EL{i}", "elective", units=4) for i in range(6)]
    courses = _mandatory_and_choice_courses() + electives
    completed = tuple(cs.CORE_MANDATORY) + tuple(sorted(cs.CORE_CHOICE_POOL))[:3] + tuple(
        c.code for c in electives
    )
    progress = degree_progress.compute(courses, completed, 52)
    assert progress.capstone_path == "elective_alternative_complete"
    assert progress.elective_units_target == cs.ELECTIVE_UNITS_BASE + (
        cs.CAPSTONE_ALTERNATIVE_ELECTIVE_COUNT * cs.TYPICAL_ELECTIVE_UNITS
    )


def test_level4000_cap_reached():
    electives = [_course("CS4221", "elective", units=4, level=4000), _course("CS4225", "elective", units=4, level=4000)]
    progress = degree_progress.compute(electives, tuple(c.code for c in electives), 8)
    assert progress.elective_level4000_used == 2
    assert progress.elective_level4000_cap_reached is True
