"""Exercises the course recommendation tool's gate.py: what it asks the
student for before or alongside answering — the target role as optional,
Vertical interest and Capstone intent as supplementary — and nothing
without the consent the course purpose needs."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.tools import input_needs as shared
from app.tools.specialist.course_recommendation import gate
from app.tools.turn_context import TurnState


def _state(**kw) -> TurnState:
    return TurnState(messages=[HumanMessage("courses?")], user_id=kw.pop("user_id", "u1"), **kw)


@pytest.fixture
def profile(monkeypatch):
    facts: dict = {}
    monkeypatch.setattr(gate, "get_profile_for_purpose", lambda uid, purpose: facts)
    monkeypatch.setattr(shared, "missing_purpose_consent", lambda uid, purpose: None)
    return facts


def _levels(needs) -> dict:
    return {n.field_key: n.level for n in needs}


def test_an_empty_profile_asks_for_the_role_first_and_the_rest_alongside(profile):
    assert _levels(gate.input_needs(_state())) == {
        "main_target_role": "optional", "track_interest": "supplementary", "capstone_intent": "supplementary",
    }


@pytest.mark.parametrize("known", [
    {"main_target_role": "data_analytics"},
    {"target_role_families": ["data_analytics"]},
])
def test_a_known_role_isnt_asked_for(profile, known):
    profile.update(known)
    assert "main_target_role" not in _levels(gate.input_needs(_state()))


def test_a_role_named_in_the_message_isnt_asked_for(profile):
    assert "main_target_role" not in _levels(gate.input_needs(_state(target_role_hint="quant")))


def test_known_supplementary_facts_arent_asked_for(profile):
    profile.update({"track_interest": ["computing_technologies"], "capstone_intent": "capstone_research"})
    assert _levels(gate.input_needs(_state())) == {"main_target_role": "optional"}


def test_nothing_is_asked_without_the_consent(monkeypatch):
    monkeypatch.setattr(gate, "get_profile_for_purpose", lambda uid, purpose: {})
    monkeypatch.setattr(shared, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    assert gate.input_needs(_state()) == ()


def test_an_anonymous_turn_asks_nothing():
    assert gate.input_needs(_state(user_id="")) == ()


def test_a_semester_plan_requires_the_study_mode(profile):
    profile["main_target_role"] = "data_analytics"
    needs = gate.input_needs(_state(course_mode_hint="semester_plan"))
    assert _levels(needs)["study_mode"] == "required"


def test_a_study_mode_on_the_profile_or_in_the_message_isnt_asked_for(profile):
    assert "study_mode" not in _levels(gate.input_needs(TurnState(
        messages=[HumanMessage("我是非全日制，帮我排下学期的课")], user_id="u1", course_mode_hint="semester_plan",
    )))
    profile["study_mode"] = "part_time"
    assert "study_mode" not in _levels(gate.input_needs(_state(course_mode_hint="semester_plan")))


def test_other_modes_dont_ask_for_the_study_mode(profile):
    assert "study_mode" not in _levels(gate.input_needs(_state(course_mode_hint="ad_hoc")))
