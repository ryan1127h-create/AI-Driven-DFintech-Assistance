"""A turn's sources are kept with its log entry (not in the message text the
next turns see) and come back with the conversation history."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from app.domains.conversation import service
from app.domains.conversation.models import ConversationState


class _Store:
    def __init__(self) -> None:
        self.saved = None

    def save_state(self, session_id, state):
        self.saved = state


def test_sources_are_logged_with_the_turn_and_returned_with_history(monkeypatch):
    store = _Store()
    monkeypatch.setattr(service, "get_session_store", lambda: store)
    state = ConversationState()

    sourced = AIMessage("Tuition is S$74,120.", additional_kwargs={"sources": ["https://example.edu/fees"]})
    service.record_turn("s1", state, HumanMessage("Tuition?"), sourced, ["financial"], "financial_agent")
    service.record_turn("s1", state, HumanMessage("Thanks"), AIMessage("You're welcome."), ["general"], "supervisor")

    assert store.saved.pending_turn_intents[0]["sources"] == ["https://example.edu/fees"]
    assert "sources" not in store.saved.pending_turn_intents[1]
    assert store.saved.raw_tail[1].content == "Tuition is S$74,120."  # the text later turns see stays clean

    turns = service._pair_to_turns(store.saved.raw_tail, 1, False, store.saved.pending_turn_intents)
    ai_turns = [t for t in turns if t["role"] == "ai"]
    assert [t["sources"] for t in ai_turns] == [["https://example.edu/fees"], []]
