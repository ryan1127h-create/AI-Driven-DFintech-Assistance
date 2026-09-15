"""Exercises pipeline/selection.py: STAGE 5's LLM proposal, its bounded
self-correction loop, and the deterministic fallback. The LLM call itself
(`llm.complete`) is always monkeypatched — these tests never hit a real
model.

Every slot now asks for `display_count` candidates (required_pick_count +
2, capped by how many are eligible) so the student gets real choice —
service.py, not this module, marks the first `required_pick_count` of the
returned order as the actual recommendation."""

from __future__ import annotations

import json

from app.domains.specialist.course_recommendation.errors import ErrorCode
from app.domains.specialist.course_recommendation.models import Course, RequirementSlot
from app.domains.specialist.course_recommendation.pipeline import scoring, selection
from app.domains.specialist.course_recommendation.pipeline.requirement_slots import (
    EXTRA_DISPLAY_OPTIONS,
)


def _course(code: str, skills: tuple[str, ...] = ()) -> Course:
    return Course(
        code=code, title=code, units=4, section="", skills=skills, description="",
        prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
    )


def _scored(codes: list[str]):
    courses = [_course(c) for c in codes]
    return scoring.score_slot_candidates(tuple(courses), [], (), [], [], project_averse=False)


def _slot(pick_count: int, codes: list[str]) -> RequirementSlot:
    return RequirementSlot(
        slot_id="s", slot_type="elective", label="Test slot",
        required_pick_count=pick_count,
        display_count=min(pick_count + EXTRA_DISPLAY_OPTIONS, len(codes)),
        eligible_candidates=tuple(codes),
    )


def test_display_count_is_required_plus_two_capped_by_candidates():
    slot = _slot(1, ["A", "B"])  # only 2 candidates exist, so 1+2=3 is capped to 2
    assert slot.display_count == 2
    slot2 = _slot(1, ["A", "B", "C", "D"])
    assert slot2.display_count == 3


def test_validate_picks_accepts_exact_display_count_from_eligible_codes():
    slot = _slot(1, ["A", "B", "C"])  # display_count = 3
    raw = [
        {"course_code": "A", "reason": "top pick"},
        {"course_code": "B", "reason": "alternative"},
        {"course_code": "C", "reason": "alternative"},
    ]
    picks = selection.validate_picks(raw, slot, {"A", "B", "C"})
    assert [p["course_code"] for p in picks] == ["A", "B", "C"]


def test_validate_picks_rejects_unknown_code():
    slot = _slot(1, ["A"])  # display_count = 1
    raw = [{"course_code": "ZZ9999", "reason": "hallucinated"}]
    assert selection.validate_picks(raw, slot, {"A"}) is None


def test_validate_picks_rejects_wrong_count():
    slot = _slot(2, ["A", "B", "C", "D"])  # display_count = 4
    raw = [{"course_code": "A", "reason": "ok"}]
    assert selection.validate_picks(raw, slot, {"A", "B", "C", "D"}) is None


def test_validate_picks_drops_duplicates_then_fails_count():
    slot = _slot(1, ["A", "B"])  # display_count = 2
    raw = [
        {"course_code": "A", "reason": "ok"},
        {"course_code": "A", "reason": "ok again"},
    ]
    assert selection.validate_picks(raw, slot, {"A", "B"}) is None


def test_select_for_slot_succeeds_on_first_attempt(monkeypatch):
    slot = _slot(1, ["A"])  # only 1 candidate exists -> display_count = 1
    scored = _scored(["A"])
    response = json.dumps({"recommendations": [{"course_code": "A", "reason": "good fit"}], "notes": []})
    monkeypatch.setattr(selection.llm, "complete", lambda *a, **k: response)

    outcome = selection.select_for_slot(slot, scored, None, [], request_id="r1")
    assert outcome.picks == ({"course_code": "A", "reason": "good fit"},)
    assert outcome.attempts == 1


def test_select_for_slot_retries_after_malformed_json_then_succeeds(monkeypatch):
    slot = _slot(1, ["A"])
    scored = _scored(["A"])
    responses = iter([
        "not json at all",
        json.dumps({"recommendations": [{"course_code": "A", "reason": "fixed"}]}),
    ])
    monkeypatch.setattr(selection.llm, "complete", lambda *a, **k: next(responses))

    outcome = selection.select_for_slot(slot, scored, None, [], request_id="r1")
    assert outcome.picks == ({"course_code": "A", "reason": "fixed"},)
    assert outcome.attempts == 2


def test_select_for_slot_gives_up_after_max_attempts(monkeypatch):
    slot = _slot(1, ["A"])
    scored = _scored(["A"])
    bad_response = json.dumps({"recommendations": [{"course_code": "ZZ9999", "reason": "wrong"}]})
    monkeypatch.setattr(selection.llm, "complete", lambda *a, **k: bad_response)

    outcome = selection.select_for_slot(slot, scored, None, [], request_id="r1")
    assert outcome.picks is None
    assert outcome.error_code == ErrorCode.SLOT_VALIDATION_FAILED
    assert outcome.attempts == selection.MAX_ATTEMPTS
    assert outcome.retryable is True


def test_select_for_slot_handles_llm_exception_without_retry(monkeypatch):
    slot = _slot(1, ["A"])
    scored = _scored(["A"])

    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(selection.llm, "complete", _raise)

    outcome = selection.select_for_slot(slot, scored, None, [], request_id="r1")
    assert outcome.picks is None
    assert outcome.error_code == ErrorCode.SLOT_LLM_SELECTION_FAILED
    assert outcome.attempts == 1


def test_fallback_for_slot_shows_more_than_required():
    slot = _slot(1, ["A", "B", "C"])  # display_count = 3, required = 1
    scored = _scored(["A", "B", "C"])
    picks = selection.fallback_for_slot(slot, scored)
    assert len(picks) == 3  # shows the extra 2 alternatives, not just the 1 required
    assert picks[0]["course_code"] == scored[0].course.code  # best-scored leads


def test_fallback_for_slot_two_pick_uses_best_pair_for_the_leading_two():
    a = _course("A", skills=("data_analytics",))
    b = _course("B", skills=("data_analytics",))
    c = _course("C", skills=("security",))
    scored = scoring.score_slot_candidates(
        (a, b, c), [], ("data_analytics", "security"), [], [], project_averse=False,
    )
    slot = _slot(2, ["A", "B", "C"])  # display_count = min(2+2, 3) = 3
    picks = selection.fallback_for_slot(slot, scored)
    assert len(picks) == 3
    # the leading pair (the actual recommendation) should be the
    # skill-diverse one, not the two individually top-scored courses
    leading_pair = {picks[0]["course_code"], picks[1]["course_code"]}
    assert "C" in leading_pair


def test_pick_instruction_for_optional_secondary_slot():
    slot = _slot(0, ["A", "B"])  # required=0 -> secondary/optional group
    prompt = selection._pick_instruction(slot)
    assert "None of these are required" in prompt
    assert str(slot.display_count) in prompt
