"""Exercises stages/s5_scoring/selection.py: S5's deterministic selection
within one requirement slot — display order, the 2-pick complementarity
check, and reasons built from the score breakdown.

Every slot asks for `display_count` candidates (required_pick_count + 2,
capped by how many are eligible) so the student gets real choice — the
first `required_pick_count` picks are the recommendation."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, RequirementSlot
from app.domains.specialist.course_recommendation.policy.tuning import EXTRA_DISPLAY_OPTIONS
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer, selection


def _course(code: str, skills: tuple[str, ...] = ()) -> Course:
    return Course(
        code=code, title=code, units=4, section="", skills=skills, description="",
        prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
    )


def _scored(courses: list[Course], skill_gaps: tuple[str, ...] = ()):
    return scorer.score_slot_candidates(tuple(courses), [], skill_gaps, [], [], project_averse=False)


def _slot(pick_count: int, codes: list[str]) -> RequirementSlot:
    return RequirementSlot(
        slot_id="s", slot_type="elective", label="Test slot",
        required_pick_count=pick_count,
        display_count=min(pick_count + EXTRA_DISPLAY_OPTIONS, len(codes)),
        eligible_candidates=tuple(codes),
    )


def test_display_count_is_required_plus_two_capped_by_candidates():
    assert _slot(1, ["A", "B"]).display_count == 2  # 1+2=3, capped to the 2 that exist
    assert _slot(1, ["A", "B", "C", "D"]).display_count == 3


def test_select_shows_more_than_required_best_first():
    courses = [_course("A"), _course("B", skills=("finance",)), _course("C")]
    scored = _scored(courses, skill_gaps=("finance",))
    picks = selection.select_for_slot(_slot(1, ["A", "B", "C"]), scored)
    assert [p.scored.course.code for p in picks] == ["B", "A", "C"]  # best first, then by code


def test_two_pick_slot_leads_with_the_skill_diverse_pair():
    a = _course("A", skills=("data_analytics",))
    b = _course("B", skills=("data_analytics",))
    c = _course("C", skills=("security",))
    scored = _scored([a, b, c], skill_gaps=("data_analytics", "security"))
    picks = selection.select_for_slot(_slot(2, ["A", "B", "C"]), scored)
    assert len(picks) == 3
    assert "C" in {picks[0].scored.course.code, picks[1].scored.course.code}


def test_best_pair_none_with_fewer_than_two_candidates():
    assert selection.best_pair(_scored([_course("A")])) is None


def test_reason_is_built_from_the_breakdown():
    scored = _scored([_course("A", skills=("finance",))], skill_gaps=("finance",))
    [pick] = selection.select_for_slot(_slot(1, ["A"]), scored)
    assert pick.reason == "Closes skill gaps: finance."


def test_reason_falls_back_to_the_requirement_when_no_signal_fired():
    [pick] = selection.select_for_slot(_slot(1, ["A"]), _scored([_course("A")]))
    assert pick.reason == "Counts toward Test slot."
