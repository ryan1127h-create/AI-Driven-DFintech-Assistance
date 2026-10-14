"""The user's assistant preferences in a chat turn: the reply language
(the message's own language first, the saved preference only when that
can't be told) and the answer detail (one prompt line where answers are
written)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core import answer_depth
from app.domains.auth import interface as auth_interface
from app.domains.specialist.knowledge_qa import qa_agent
from app.orchestrator import classification, turn_service


# --- reply language -------------------------------------------------------------

@pytest.mark.parametrize("detected, preferred, expected", [
    ("zh", ["en"], "zh"),         # the message's language wins
    (None, ["ja", "en"], "ja"),   # can't tell: first preference
    (None, [], "en"),             # nothing to go on: English
])
def test_reply_language(detected, preferred, expected):
    assert turn_service.resolve_reply_language(detected, preferred) == expected


def test_classifier_leaves_the_language_open_when_it_cannot_tell(monkeypatch):
    replies = iter(['{"intents": ["general"], "target_role_hint": null, "program_hints": [], "reply_language": null}'])
    monkeypatch.setattr(classification.llm, "complete", lambda *a, **k: next(replies))
    assert classification.classify_intent([HumanMessage("ok")])[3] is None

    def broken(*a, **k):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(classification.llm, "complete", broken)
    assert classification.classify_intent([HumanMessage("学费多少")])[3] is None


# --- answer depth -----------------------------------------------------------------

def test_answer_depth_lines_and_budgets():
    assert answer_depth.instruction("standard") == "" and answer_depth.with_instruction("P", "standard") == "P"
    assert "concise" in answer_depth.with_instruction("P", "concise")
    assert "never invent" in answer_depth.instruction("detailed")
    assert answer_depth.max_tokens("detailed", 2000) == 3000
    assert answer_depth.max_tokens("concise", 2000) == 2000  # kept short by the instruction, not truncation
    assert answer_depth.normalize("verbose") == "standard"


def test_knowledge_answers_carry_the_depth_line(monkeypatch):
    seen = {}

    def stream(system_prompt, history, **kwargs):
        seen.update(prompt=system_prompt, max_tokens=kwargs["max_tokens"])
        yield "ok"
    monkeypatch.setattr(qa_agent.llm, "stream", stream)

    qa_agent.answer("Role.", "Tuition?", [], context="Fees: S$74,120.", depth="concise")
    assert answer_depth.instruction("concise") in seen["prompt"]
    qa_agent.answer("Role.", "Tuition?", [], context="Fees: S$74,120.")
    assert "Answer length" not in seen["prompt"]


# --- preferences reach the turn -----------------------------------------------------------

def test_preferences_default_when_settings_cannot_be_read(monkeypatch):
    def broken(user_id):
        raise RuntimeError("db down")
    monkeypatch.setattr(auth_interface.repository, "get_settings", broken)
    assert auth_interface.get_assistant_preferences("u1") == {"language_pref": [], "answer_depth": "standard"}


def test_a_turn_uses_the_saved_preferences(monkeypatch):
    state = SimpleNamespace(history_summaries=[], raw_tail=[], declined_fields=[])
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "new_session_id", lambda: "s1")
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state)
    monkeypatch.setattr(conv, "render_summaries", lambda summaries: "")
    monkeypatch.setattr(conv, "record_turn", lambda *a, **k: None)
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "")
    monkeypatch.setattr(turn_service, "get_assistant_preferences",
                        lambda uid: {"language_pref": ["zh"], "answer_depth": "detailed"})
    monkeypatch.setattr(turn_service.classification, "classify_intent",
                        lambda messages, on_event=None, previous_turn=None: (["financial"], None, [], None, None, None))
    captured = {}

    def answer_turn(turn_state, intents, on_event=None):
        captured["state"] = turn_state
        return AIMessage("ok"), "ok", "financial_agent"
    monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)

    turn_service.run_turn(None, "ok", "u1")
    assert (captured["state"].reply_language, captured["state"].answer_depth) == ("zh", "detailed")
