"""Exercises stages/s5_scoring/scorer.py and signals.py: S5's per-slot
multi-signal scoring and its auditable breakdown."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer as scoring


def _course(code: str, skills: tuple[str, ...] = (), workload_shape=None, title: str = "", section: str = "", description: str = "") -> Course:
    return Course(
        code=code,
        title=title or code,
        units=4,
        section=section,
        skills=skills,
        description=description,
        prerequisite_text="",
        preclusion_text="",
        can_recommend=True,
        source_url="",
        workload_shape=workload_shape,
    )


def test_gap_skill_outweighs_preference_outweighs_role_skill():
    # Weights carried forward from the original rule_engine.py design:
    # gap (2.0) > preference (1.5) > role-skill coverage alone (1.0).
    gap_course = _course("A", skills=("finance",))
    role_course = _course("B", skills=("programming",))
    pref_course = _course("C", title="Great intro to trading")
    scored = scoring.score_slot_candidates(
        (pref_course, role_course, gap_course),
        role_skills=["finance", "programming"],
        skill_gaps=("finance",),
        preferences=["intro to trading"],
        curated_role_courses=[],
        project_averse=False,
    )
    assert [s.course.code for s in scored] == ["A", "C", "B"]


def test_curated_role_course_gets_a_bonus():
    plain = _course("A")
    curated = _course("B")
    scored = scoring.score_slot_candidates(
        (plain, curated), [], (), [], curated_role_courses=["B"], project_averse=False,
    )
    by_code = {s.course.code: s for s in scored}
    assert by_code["B"].score > by_code["A"].score
    assert by_code["B"].curated_match is True


def test_project_heavy_course_penalized_when_student_is_project_averse():
    heavy = _course("FT5007", workload_shape="project_heavy")
    scored = scoring.score_slot_candidates((heavy,), [], (), [], [], project_averse=True)
    assert scored[0].score < 0
    assert scored[0].workload_note is not None


def test_project_heavy_course_not_penalized_when_no_preference_given():
    heavy = _course("FT5007", workload_shape="project_heavy")
    scored = scoring.score_slot_candidates((heavy,), [], (), [], [], project_averse=False)
    assert scored[0].score == 0
    assert scored[0].workload_note is None


def test_matched_skills_are_the_role_relevant_ones_in_course_order():
    course = _course("A", skills=("security", "finance", "programming"))
    scored = scoring.score_slot_candidates((course,), ["finance", "security"], ("security",), [], [], project_averse=False)
    assert scored[0].matched_skills == ["security", "finance"]


def test_score_is_the_sum_of_its_breakdown():
    course = _course("A", skills=("finance", "programming"), workload_shape="project_heavy", description="blockchain intro")
    scored = scoring.score_slot_candidates(
        (course,), ["finance", "programming"], ("finance",), ["blockchain"], ["A"], project_averse=True,
    )[0]
    signals = {item.signal: item.delta for item in scored.breakdown}
    assert signals == {
        "skill_gap": 2.0, "role_skill": 1.0, "preference": 1.5,
        "curated_role_course": 1.0, "project_heavy": -1.0,
    }
    assert scored.score == sum(signals.values())
    assert scored.workload_note == "This course is primarily independent project work."


def test_no_signal_fires_without_inputs():
    scored = scoring.score_slot_candidates((_course("A", skills=("finance",)),), [], (), [], [], project_averse=False)
    assert scored[0].breakdown == () and scored[0].score == 0
