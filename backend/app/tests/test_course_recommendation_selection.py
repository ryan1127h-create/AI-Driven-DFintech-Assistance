"""Exercises stages/s5_scoring/selection.py: S5's deterministic selection
within one requirement slot — display order, the 2-pick complementarity
check, and the template reason built from the pick's evidence.

Every slot asks for `display_count` candidates (required_pick_count + 2,
capped by how many are eligible) so the student gets real choice — the
first `required_pick_count` picks are the recommendation."""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, RequirementSlot
from app.domains.specialist.course_recommendation.policy.tuning import EXTRA_DISPLAY_OPTIONS
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer, selection, signals
from app.domains.specialist.course_recommendation.stages.s5_scoring.evidence import EvidenceContext

CTX = EvidenceContext(target_role=None, skill_share={}, prerequisite_cautions=frozenset())


def _course(code: str, skills: tuple[str, ...] = (), roles: tuple[str, ...] = ()) -> Course:
    return Course(
        code=code, title=code, units=4, section="", skills=skills, description="",
        prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
        role_tags=tuple((role, role) for role in roles),
    )


def _scored(courses: list[Course], skill_gaps: tuple[str, ...] = ()):
    ctx = signals.ScoringContext(
        target_role_tag=None, role_skills=(), skill_gaps=frozenset(skill_gaps),
        skill_share={s: 0.3 for c in courses for s in c.skills}, preferences=(), project_averse=False,
    )
    return scorer.score_slot_candidates(tuple(courses), ctx)


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
    picks = selection.select_for_slot(_slot(1, ["A", "B", "C"]), scored, CTX)
    assert [p.scored.course.code for p in picks] == ["B", "A", "C"]  # best first, then by code


def test_two_pick_slot_breaks_a_score_tie_with_the_complementary_pair():
    # All three score the same; A and B are aimed at the same role, C at another.
    a = _course("A", skills=("finance",), roles=("quant",))
    b = _course("B", skills=("finance",), roles=("quant",))
    c = _course("C", skills=("finance",), roles=("risk",))
    scored = _scored([a, b, c], skill_gaps=("finance",))
    picks = selection.select_for_slot(_slot(2, ["A", "B", "C"]), scored, CTX)
    assert len(picks) == 3
    assert "C" in {picks[0].scored.course.code, picks[1].scored.course.code}


def test_complementarity_never_displaces_a_better_scoring_course():
    # The CS5231 case: a zero-score course spanning other roles must not
    # take a pick from a course that actually scored.
    a = _course("A", skills=("finance",), roles=("quant",))
    b = _course("B", skills=("finance",), roles=("quant",))
    c = _course("C", roles=("security",))
    scored = _scored([a, b, c], skill_gaps=("finance",))
    picks = selection.select_for_slot(_slot(2, ["A", "B", "C"]), scored, CTX)
    assert [p.scored.course.code for p in picks[:2]] == ["A", "B"]


def test_best_pair_none_with_fewer_than_two_candidates():
    assert selection.best_pair(_scored([_course("A")])) is None


def test_template_reason_is_the_evidence_as_one_sentence():
    [pick] = selection.select_for_slot(_slot(1, ["A"]), _scored([_course("A")]), CTX)
    assert pick.evidence == (
        "counts toward your remaining electives (Test slot)",
        "not on this academic year's timetable",  # the test course has no offered terms
    )
    assert pick.reason == (
        "Counts toward your remaining electives (Test slot); not on this academic year's timetable."
    )
