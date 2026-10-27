"""Exercises stages/s3_constraints/eligibility.py: S3's hard exclusion rules and the
prerequisite soft-caution signal (never an exclusion)."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course
from app.domains.specialist.course_recommendation.stages.s3_constraints import eligibility


def _course(code: str, **overrides) -> Course:
    defaults = dict(
        code=code,
        title=code,
        units=4,
        section="",
        skills=(),
        description="",
        prerequisite_text="",
        preclusion_text="",
        can_recommend=True,
        source_url="",
    )
    defaults.update(overrides)
    return Course(**defaults)


def test_completed_course_is_excluded():
    courses = [_course("FT5001")]
    pool = eligibility.build_candidate_pool(courses, ["FT5001"], [])
    assert pool.eligible == ()
    assert pool.excluded_courses[0]["reason"] == "already_completed"
    assert pool.completed_units == 4


def test_not_recommendable_course_is_excluded():
    courses = [_course("CS4221", can_recommend=False)]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert pool.eligible == ()
    assert pool.excluded_courses[0]["reason"] == "not_recommendable"


def test_needs_review_course_is_excluded():
    courses = [_course("BMF5358", data_quality="needs_review")]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert pool.eligible == ()
    assert pool.excluded_courses[0]["reason"] == "needs_review"


def test_preclusion_against_completed_course_is_excluded():
    courses = [
        _course("FT5001"),
        _course("FT5009", preclusion_text="Must not have completed: FT5001"),
    ]
    pool = eligibility.build_candidate_pool(courses, ["FT5001"], [])
    codes = {c.code for c in pool.eligible}
    assert "FT5009" not in codes
    reasons = {c["course_code"]: c["reason"] for c in pool.excluded_courses}
    assert reasons["FT5009"] == "precluded_by_completed_course"


def test_prerequisite_caution_fires_without_excluding():
    courses = [
        _course("FT5007", prerequisite_text="Must have completed IT5001X"),
        _course("IT5001X"),
    ]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert {c.code for c in pool.eligible} == {"FT5007", "IT5001X"}
    assert "FT5007" in pool.prerequisite_cautions


def test_prerequisite_caution_does_not_fire_once_prerequisite_completed():
    courses = [
        _course("FT5007", prerequisite_text="Must have completed IT5001X"),
    ]
    pool = eligibility.build_candidate_pool(courses, ["IT5001X"], [])
    assert "FT5007" in {c.code for c in pool.eligible}
    assert "FT5007" not in pool.prerequisite_cautions


def test_prerequisite_caution_does_not_fire_for_prose_with_no_course_code():
    courses = [_course("FT5001", prerequisite_text="Instructor's consent required")]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert pool.prerequisite_cautions == ()


def test_skill_gaps_exclude_covered_role_skills():
    courses = [_course("FT5005", skills=("ai_ml", "programming"))]
    pool = eligibility.build_candidate_pool(courses, ["FT5005"], ["ai_ml", "finance"])
    assert pool.skill_gaps == ("finance",)


def test_unrecognized_completed_course_is_reported_not_dropped():
    courses = [_course("FT5001")]
    pool = eligibility.build_candidate_pool(courses, ["Machine Learning", "ZZ9999"], [])
    assert "Machine Learning" in pool.completed_unrecognized
    assert "ZZ9999" in pool.completed_unrecognized


def test_6000_level_course_is_excluded_since_it_never_counts():
    courses = [_course("CS6216", level=6000), _course("CS5228", level=5000)]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert [c.code for c in pool.eligible] == ["CS5228"]
    assert pool.excluded_courses == ({"course_code": "CS6216", "reason": "level_not_countable"},)


# ---- structured prerequisites and the planned semester ------------------------

from app.domains.specialist.course_recommendation.models import PlanTerm, Session  # noqa: E402

S2 = PlanTerm(ay="2026-2027", semester=2, label="AY2026/27 Sem2")


def _runs(*semesters):
    return tuple(Session("2026-2027", s, "Lecture", "1", "Monday", "18:30", "21:30") for s in semesters)


def test_an_unmet_structured_prerequisite_is_a_caution_outside_planning():
    courses = [_course("FT5011", prerequisite_groups=(("FT5005",),), sessions=_runs(2))]
    pool = eligibility.build_candidate_pool(courses, [], [])
    assert [c.code for c in pool.eligible] == ["FT5011"] and pool.prerequisite_cautions == ("FT5011",)


def test_an_unmet_prerequisite_excludes_the_course_from_a_semester_plan():
    courses = [_course("FT5011", prerequisite_groups=(("FT5005",),), sessions=_runs(2))]
    pool = eligibility.build_candidate_pool(courses, [], [], term=S2)
    assert pool.eligible == ()
    assert pool.excluded_courses == (
        {"course_code": "FT5011", "reason": "prerequisite_unmet", "related_course_code": "FT5005"},
    )


def test_any_course_of_a_group_meets_it():
    courses = [_course("IT5001X"), _course("IT5006", prerequisite_groups=(("IT5001", "IT5001X"),), sessions=_runs(2))]
    pool = eligibility.build_candidate_pool(courses, ["IT5001X"], [], term=S2)
    assert [c.code for c in pool.eligible] == ["IT5006"] and pool.prerequisite_cautions == ()


def test_a_course_not_running_in_the_planned_semester_is_excluded():
    courses = [_course("FT5009", sessions=_runs(1)), _course("IS5009", sessions=_runs(2))]
    pool = eligibility.build_candidate_pool(courses, [], [], term=S2)
    assert [c.code for c in pool.eligible] == ["IS5009"]
    assert {"course_code": "FT5009", "reason": "not_offered_in_term"} in pool.excluded_courses


def test_without_that_semesters_timetable_nothing_is_excluded_for_timing():
    courses = [_course("FT5009", sessions=_runs(1))]
    pool = eligibility.build_candidate_pool(courses, [], [], term=PlanTerm("2027-2028", 1, "AY2027/28 Sem1"))
    assert [c.code for c in pool.eligible] == ["FT5009"]
    assert any("timetable for AY2027/28 Sem1 isn't published yet" in note for note in pool.notes)
