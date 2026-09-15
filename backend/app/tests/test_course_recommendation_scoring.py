"""Exercises pipeline/scoring.py: STAGE 5's per-slot multi-signal scoring
and the 2-pick complementarity re-rank."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course
from app.domains.specialist.course_recommendation.pipeline import scoring


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


def test_best_pair_prefers_skill_diversity_over_raw_top_two():
    # A and B both teach the same single skill; C is slightly lower-scored
    # individually but covers a different skill entirely alongside A.
    a = _course("A", skills=("data_analytics",))
    b = _course("B", skills=("data_analytics",))
    c = _course("C", skills=("security",))
    scored = scoring.score_slot_candidates(
        (a, b, c), [], ("data_analytics", "security"), [], [], project_averse=False,
    )
    pair = scoring.best_pair(scored)
    assert pair is not None
    codes = {sc.course.code for sc in pair}
    assert codes == {"A", "C"} or codes == {"B", "C"}


def test_best_pair_none_with_fewer_than_two_candidates():
    scored = scoring.score_slot_candidates((_course("A"),), [], (), [], [], project_averse=False)
    assert scoring.best_pair(scored) is None


def test_matched_skills_of_intersects_role_skills():
    course = _course("A", skills=("finance", "programming"))
    assert scoring.matched_skills_of(course, ["finance", "security"]) == ["finance"]
