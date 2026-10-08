"""Exercises stages/s5_scoring/scorer.py and signals.py: S5's per-slot
multi-signal scoring and its auditable breakdown — role fit from the
course's own role tags, skill signals only for distinctive skills."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer as scoring
from app.domains.specialist.course_recommendation.stages.s5_scoring import signals

# Every skill these tests use counts as distinctive unless a test says otherwise.
RARE = {"finance": 0.3, "programming": 0.3, "security": 0.3, "data_analytics": 0.3}


def _course(code: str, skills: tuple[str, ...] = (), workload_shape=None, title: str = "",
            description: str = "", role_tags: tuple[tuple[str, str], ...] = ()) -> Course:
    return Course(
        code=code, title=title or code, units=4, section="", skills=skills, description=description,
        prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
        workload_shape=workload_shape, role_tags=role_tags,
    )


def _ctx(target_role_tag=None, role_skills=(), skill_gaps=(), skill_share=None, preferences=(), project_averse=False):
    return signals.ScoringContext(
        target_role_tag=target_role_tag, role_skills=tuple(role_skills), skill_gaps=frozenset(skill_gaps),
        skill_share=RARE if skill_share is None else skill_share, preferences=tuple(preferences),
        project_averse=project_averse,
    )


def test_gap_skill_outweighs_preference_outweighs_role_skill():
    gap_course = _course("A", skills=("finance",))
    role_course = _course("B", skills=("programming",))
    pref_course = _course("C", title="Great intro to trading")
    scored = scoring.score_slot_candidates(
        (pref_course, role_course, gap_course),
        _ctx(role_skills=["finance", "programming"], skill_gaps=("finance",), preferences=["intro to trading"]),
    )
    assert [s.course.code for s in scored] == ["A", "C", "B"]


def test_a_course_tagged_for_the_target_role_outranks_derived_skill_matches():
    # The IS5008 case: tagged for other roles, but its derived skills
    # include two of the data-analytics role's skills.
    tagged = _course("IS4261", role_tags=(("data_analytics", "Data Analytics"),))
    derived = _course("IS5008", skills=("data_analytics", "finance"), role_tags=(("risk_management", "Risk Management"),))
    scored = scoring.score_slot_candidates(
        (derived, tagged), _ctx("data_analytics", role_skills=["data_analytics", "finance"]),
    )
    assert [s.course.code for s in scored] == ["IS4261", "IS5008"]
    assert scored[0].role_tag_match is True and scored[1].role_tag_match is False


def test_common_skills_score_nothing():
    course = _course("A", skills=("programming", "security"))
    ctx = _ctx(role_skills=["programming", "security"], skill_gaps=("programming",),
               skill_share={"programming": 0.9, "security": 0.38})
    scored = scoring.score_slot_candidates((course,), ctx)[0]
    assert {item.signal: item.delta for item in scored.breakdown} == {"role_skill": 1.0}


def test_project_heavy_course_penalized_when_student_is_project_averse():
    heavy = _course("FT5007", workload_shape="project_heavy")
    scored = scoring.score_slot_candidates((heavy,), _ctx(project_averse=True))
    assert scored[0].score < 0
    assert scored[0].workload_note is not None


def test_project_heavy_course_not_penalized_when_no_preference_given():
    heavy = _course("FT5007", workload_shape="project_heavy")
    scored = scoring.score_slot_candidates((heavy,), _ctx())
    assert scored[0].score == 0
    assert scored[0].workload_note is None


def test_matched_skills_are_the_role_relevant_ones_in_course_order():
    course = _course("A", skills=("security", "finance", "programming"))
    scored = scoring.score_slot_candidates((course,), _ctx(role_skills=["finance", "security"], skill_gaps=("security",)))
    assert scored[0].matched_skills == ["security", "finance"]


def test_score_is_the_sum_of_its_breakdown():
    course = _course("A", skills=("finance", "programming"), workload_shape="project_heavy",
                     description="blockchain intro", role_tags=(("data_analytics", "Data Analytics"),))
    scored = scoring.score_slot_candidates((course,), _ctx(
        "data_analytics", role_skills=["finance", "programming"], skill_gaps=("finance",),
        preferences=["blockchain"], project_averse=True,
    ))[0]
    deltas = {item.signal: item.delta for item in scored.breakdown}
    assert deltas == {
        "role_tag": 3.0, "skill_gap": 2.0, "role_skill": 1.0, "preference": 1.5, "project_heavy": -1.0,
    }
    assert scored.score == sum(deltas.values())
    assert scored.workload_note == "This course is primarily independent project work."


def test_no_signal_fires_without_inputs():
    scored = scoring.score_slot_candidates((_course("A", skills=("finance",)),), _ctx())
    assert scored[0].breakdown == () and scored[0].score == 0


def test_skill_shares_count_only_recommendable_courses():
    courses = [_course("A", skills=("finance",)), _course("B"),
               Course(code="C", title="C", units=4, section="", skills=("finance",), description="",
                      prerequisite_text="", preclusion_text="", can_recommend=False, source_url="")]
    assert signals.skill_shares(courses) == {"finance": 0.5}
