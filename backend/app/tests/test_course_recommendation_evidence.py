"""Exercises stages/s5_scoring/evidence.py: the synopsis and the evidence a
recommendation is explained with — direct role tags rather than derived
skills, only distinctive skills, and the requirement/teaching/timing facts."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, RequirementSlot, ScoredCourse
from app.domains.specialist.course_recommendation.policy import tuning
from app.domains.specialist.course_recommendation.stages.s5_scoring import evidence

DATA_ANALYTICS = ("data_analytics", "Data Analytics")


def _course(code: str, **overrides) -> Course:
    defaults = dict(
        code=code, title=code, units=4, section="", skills=(), description="",
        prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
        offered_terms=("Semester 1 (2026-2027)", "Semester 2 (2026-2027)"),
    )
    defaults.update(overrides)
    return Course(**defaults)


def _scored(course: Course, gaps: tuple[str, ...] = (), role: tuple[str, ...] = ()) -> ScoredCourse:
    return ScoredCourse(course=course, score=0.0, matched_gap_skills=gaps, matched_role_skills=role,
                        matched_preferences=(), curated_match=False)


def _slot(slot_type: str = "elective", pick_count: int = 1, candidates: tuple[str, ...] = ("A",), label: str = "Vertical #1") -> RequirementSlot:
    return RequirementSlot(slot_id="s", slot_type=slot_type, label=label, required_pick_count=pick_count,
                           display_count=len(candidates), eligible_candidates=candidates)


def _ctx(target_role=DATA_ANALYTICS, shares=None, cautions=()) -> evidence.EvidenceContext:
    return evidence.EvidenceContext(target_role=target_role, skill_share=shares or {},
                                    prerequisite_cautions=frozenset(cautions))


def test_synopsis_keeps_whole_opening_sentences_within_the_limit():
    text = "First sentence here. Second one too. " + "Third sentence is very long. " * 20
    result = evidence.synopsis(text)
    assert result.startswith("First sentence here. Second one too.")
    assert len(result) <= tuning.SYNOPSIS_MAX_CHARS and result.endswith(".")


def test_synopsis_cuts_an_overlong_first_sentence_at_a_word():
    result = evidence.synopsis("word " * 100)
    assert len(result) <= tuning.SYNOPSIS_MAX_CHARS + 1 and result.endswith("word…")
    assert evidence.synopsis("   ") == ""


def test_a_course_aimed_at_other_roles_is_not_said_to_fit_the_target_role():
    # IS5008's real tags: its derived skills include data_analytics (via the
    # risk_management tag), but the course isn't aimed at data analytics.
    course = _course("IS5008", role_tags=(("cybersecurity", "Cybersecurity"), ("risk_management", "Risk Management")),
                     skills=("security", "programming", "data_analytics", "finance"))
    facts = evidence.evidence_for(_scored(course, role=("data_analytics",)), _slot(), _ctx(shares={"data_analytics": 0.79}))
    assert "aimed at Cybersecurity, Risk Management roles rather than Data Analytics" in facts
    assert not any("data analytics" in fact for fact in facts)


def test_a_course_tagged_for_the_target_role_says_so():
    course = _course("FT5009", role_tags=(("data_analytics", "Data Analytics"), ("quantitative_finance", "Quantitative Finance")))
    facts = evidence.evidence_for(_scored(course), _slot(), _ctx())
    assert "tagged for your target role, Data Analytics, and also for Quantitative Finance" in facts


def test_only_distinctive_skills_are_named():
    course = _course("A", skills=("programming", "ai_ml"))
    shares = {"programming": 0.9, "ai_ml": 0.34}
    facts = evidence.evidence_for(_scored(course, gaps=("programming", "ai_ml")), _slot(), _ctx(shares=shares))
    assert "builds AI and machine learning, a gap for your target role" in facts
    assert not any("programming" in fact for fact in facts)


def test_requirement_teaching_timing_and_prerequisite_facts():
    course = _course("FT5011", workload_shape="lecture_heavy", offered_terms=("Semester 1 (2026-2027)",),
                     prerequisite_text="Must have completed FT5005")
    slot = _slot("core_mandatory", 2, ("IT5006", "BMD5302", "FT5011"))
    facts = evidence.evidence_for(_scored(course), slot, _ctx(target_role=None))
    assert facts == (
        "one of the 3 mandatory core courses you still need",
        "taught mostly through lectures and tutorials",
        "offered only in Semester 1 (2026-2027)",
        "its prerequisite is already met",
    )


def test_an_unconfirmed_prerequisite_is_left_to_the_caution():
    course = _course("FT5011", prerequisite_text="Must have completed FT5005")
    facts = evidence.evidence_for(_scored(course), _slot(), _ctx(cautions=("FT5011",)))
    assert not any("prerequisite" in fact for fact in facts)


def test_optional_and_unscheduled_courses():
    course = _course("B", offered_terms=())
    facts = evidence.evidence_for(_scored(course), _slot(pick_count=0, label="Vertical #2"), _ctx())
    assert facts == ("an optional elective in Vertical #2", "not on this academic year's timetable")


def test_skill_shares_count_only_recommendable_courses():
    courses = [_course("A", skills=("finance",)), _course("B"), _course("C", skills=("finance",), can_recommend=False)]
    assert evidence.skill_shares(courses) == {"finance": 0.5}


def test_a_mandatory_course_off_the_target_role_gets_no_role_remark():
    course = _course("BMD5302", role_tags=(("finance_investment", "Finance & Investment"),))
    slot = _slot("core_mandatory", 2, ("IT5006", "BMD5302"))
    facts = evidence.evidence_for(_scored(course), slot, _ctx())
    assert facts == ("one of the 2 mandatory core courses you still need",)
