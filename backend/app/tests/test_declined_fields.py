"""Fields the user skipped or dismissed are remembered for the conversation:
they're saved with its state, and every later turn's TurnState carries
them, so the requirements gate doesn't ask for them again."""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app.domains.conversation.models import ConversationState, state_from_json, state_to_json
from app.orchestrator import turn_service


def test_declined_fields_survive_saving_the_state():
    state = ConversationState(declined_fields=["main_target_role"])
    assert state_from_json(state_to_json(state)).declined_fields == ["main_target_role"]
    assert state_from_json({}).declined_fields == []


def test_a_turn_adds_newly_declined_fields_to_those_already_declined(monkeypatch):
    state = SimpleNamespace(history_summaries=[], raw_tail=[], declined_fields=["track_interest"])
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "new_session_id", lambda: "s1")
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state)
    monkeypatch.setattr(conv, "render_summaries", lambda summaries: "")
    monkeypatch.setattr(conv, "record_turn", lambda *a, **k: None)
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "")
    monkeypatch.setattr(turn_service, "get_assistant_preferences",
                        lambda uid: {"language_pref": [], "answer_depth": "standard"})
    monkeypatch.setattr(turn_service.classification, "classify_intent",
                        lambda messages, on_event=None, previous_turn=None: turn_service.classification.Classification(["course_recommendation"]))
    captured = {}

    def answer_turn(turn_state, intents, on_event=None):
        captured["state"] = turn_state
        return AIMessage("ok"), "ok", "course_recommendation_agent"
    monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)

    turn_service.run_turn(None, "courses?", "u1", declined_fields=["main_target_role"])
    assert captured["state"].declined_fields == frozenset({"track_interest", "main_target_role"})
    assert state.declined_fields == ["main_target_role", "track_interest"]  # saved with the turn
