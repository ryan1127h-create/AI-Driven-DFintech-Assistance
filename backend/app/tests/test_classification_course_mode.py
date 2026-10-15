"""classification.classify_intent's course_mode_hint and career_mode_hint:
each kept only for its own intent and only when it's one of the known
modes."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from app.orchestrator import classification


def _classify(monkeypatch, **reply):
    payload = {"target_role_hint": None, "program_hints": [], "reply_language": "en", **reply}
    monkeypatch.setattr(classification.llm, "complete", lambda *a, **k: json.dumps(payload))
    return classification.classify_intent([HumanMessage("recommend practical Python courses")])


@pytest.mark.parametrize("mode", ["degree_overview", "ad_hoc", "semester_plan"])
def test_a_known_mode_is_kept_for_a_course_recommendation(monkeypatch, mode):
    assert _classify(monkeypatch, intents=["course_recommendation"], course_mode_hint=mode)[4] == mode


def test_an_unknown_mode_is_dropped(monkeypatch):
    assert _classify(monkeypatch, intents=["course_recommendation"], course_mode_hint="timetable")[4] is None


def test_a_mode_without_a_course_recommendation_is_dropped(monkeypatch):
    assert _classify(monkeypatch, intents=["academic"], course_mode_hint="ad_hoc")[4] is None


def test_a_missing_mode_is_none(monkeypatch):
    assert _classify(monkeypatch, intents=["course_recommendation"])[4] is None


def test_classification_failure_gives_no_mode(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(classification.llm, "complete", broken)
    assert classification.classify_intent([HumanMessage("courses?")]) == (["general"], None, [], None, None, None)


@pytest.mark.parametrize("mode", ["exploration", "plan", "compare"])
def test_a_known_career_mode_is_kept_for_career_advice(monkeypatch, mode):
    result = _classify(monkeypatch, intents=["career"], career_mode_hint=mode)
    assert result[5] == mode and result[4] is None


def test_an_unknown_or_misplaced_career_mode_is_dropped(monkeypatch):
    assert _classify(monkeypatch, intents=["career"], career_mode_hint="roadmap")[5] is None
    assert _classify(monkeypatch, intents=["course_recommendation"], career_mode_hint="plan")[5] is None
