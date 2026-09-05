"""Exercises evaluate_branch_tool.py's handler directly (not through the
registry): correct parsing of each action, and that every failure mode
(LLM error, malformed JSON, unrecognized action, missing note, empty
inputs) degrades to the default "accept" verdict rather than raising."""

from __future__ import annotations

from app.tools import evaluate_branch_tool as ebt
from app.tools.evaluate_branch_tool import EvaluateBranchInput


def _input(draft_text: str = "Tuition is S$74,120.", intent: str = "financial", user_message: str = "What's the fee?") -> EvaluateBranchInput:
    return EvaluateBranchInput(intent=intent, user_message=user_message, draft_text=draft_text)


def test_accept_json_returns_default_verdict(monkeypatch):
    monkeypatch.setattr(ebt.llm, "complete", lambda *a, **k: '{"action": "accept"}')
    verdict = ebt._handler(_input())
    assert verdict.action == "accept"
    assert verdict.note == ""


def test_clarify_action_carries_the_question(monkeypatch):
    monkeypatch.setattr(
        ebt.llm, "complete",
        lambda *a, **k: '{"action": "clarify", "note": "Which intake are you asking about?"}',
    )
    verdict = ebt._handler(_input(intent="admissions", user_message="When are deadlines?"))
    assert verdict.action == "clarify"
    assert verdict.note == "Which intake are you asking about?"


def test_retry_action_carries_the_gap(monkeypatch):
    monkeypatch.setattr(
        ebt.llm, "complete",
        lambda *a, **k: '{"action": "retry", "note": "only answered the fee amount, not the deadline"}',
    )
    verdict = ebt._handler(_input())
    assert verdict.action == "retry"
    assert "deadline" in verdict.note


def test_malformed_json_defaults_to_accept(monkeypatch):
    monkeypatch.setattr(ebt.llm, "complete", lambda *a, **k: "not json at all")
    assert ebt._handler(_input()).action == "accept"


def test_llm_error_defaults_to_accept(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(ebt.llm, "complete", _boom)
    assert ebt._handler(_input()).action == "accept"


def test_unrecognized_action_defaults_to_accept(monkeypatch):
    monkeypatch.setattr(ebt.llm, "complete", lambda *a, **k: '{"action": "reject_everything"}')
    assert ebt._handler(_input()).action == "accept"


def test_clarify_with_no_note_defaults_to_accept(monkeypatch):
    monkeypatch.setattr(ebt.llm, "complete", lambda *a, **k: '{"action": "clarify", "note": ""}')
    assert ebt._handler(_input()).action == "accept"


def test_empty_inputs_skip_the_llm_call_entirely(monkeypatch):
    calls = []
    monkeypatch.setattr(ebt.llm, "complete", lambda *a, **k: calls.append(1) or '{"action": "accept"}')
    assert ebt._handler(_input(user_message="")).action == "accept"
    assert ebt._handler(_input(draft_text="")).action == "accept"
    assert calls == []


def test_the_intent_placeholder_is_filled_into_the_prompt(monkeypatch):
    seen = {}

    def _fake_complete(system_prompt, payload, **kwargs):
        seen["system_prompt"] = system_prompt
        return '{"action": "accept"}'

    monkeypatch.setattr(ebt.llm, "complete", _fake_complete)
    ebt._handler(_input(intent="career"))
    assert '"career"' in seen["system_prompt"]
