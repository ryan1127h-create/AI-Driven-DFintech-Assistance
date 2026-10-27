"""A conversation's whole life: turns recorded, the oldest block frozen
into a summary and archived, and the full transcript read back — with the
in-memory store and with the Supabase store's own archive format; plus the
cache-aside order (database first)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, messages_to_dict

from app.domains.conversation import repository, service
from app.domains.conversation.models import ConversationState


@pytest.fixture
def store(monkeypatch):
    memory = repository.InMemoryConversationStore()
    monkeypatch.setattr(service, "get_session_store", lambda: memory)
    monkeypatch.setattr(service.settings, "history_block_size", 2)
    monkeypatch.setattr(service.settings, "history_raw_tail_max", 3)
    monkeypatch.setattr(service, "summarize_block", lambda messages, log=None, start=1: "earlier summary")
    return memory


def _turn(state, i):
    extra = {"sources": [f"https://src/{i}"]}
    service.record_turn("s1", state, HumanMessage(f"q{i}"), AIMessage(f"a{i}", additional_kwargs=extra),
                        ["faq"], "faq_agent")


def test_a_frozen_conversation_still_reads_back_turn_by_turn(store):
    state = ConversationState(user_id="u1")
    for i in range(1, 4):
        _turn(state, i)
    assert service.should_freeze(store.get_state("s1"))
    service.freeze_and_unlock("s1")

    history = service.get_conversation_history("s1", "u1")
    assert history["archived_turn_count"] == 2 and history["summaries"][0]["summary"] == "earlier summary"
    ai_turns = [t for t in history["turns"] if t["role"] == "ai"]
    assert [t["content"] for t in ai_turns] == ["a1", "a2", "a3"]
    assert [t["archived"] for t in ai_turns] == [True, True, False]
    assert [t["sources"] for t in ai_turns] == [["https://src/1"], ["https://src/2"], ["https://src/3"]]


class _ArchiveDB:
    """chat.messages as Postgres keeps it: archived_blocks and turn_intents
    each grow by jsonb `||`, so turn_intents is one flat list of entries."""

    def __init__(self):
        self.blocks, self.intents = [], []

    def execute(self, sql, params):
        _, blocks, intents = params
        self.blocks += json.loads(blocks)
        self.intents += json.loads(intents)

    def fetch_one(self, sql, params):
        return (self.blocks, self.intents)


def test_the_supabase_archive_gives_each_block_its_own_turns(monkeypatch):
    db = _ArchiveDB()
    monkeypatch.setattr(repository, "chat_db", db)
    store = repository.SupabaseConversationStore()
    for start in (1, 3):
        block = service.HistoryBlock(start_turn=start, end_turn=start + 1, summary="s", created_at="t")
        messages = [HumanMessage("q"), AIMessage("a"), HumanMessage("q"), AIMessage("a")]
        store.archive_block("s1", block, messages, [{"turn": start, "intents": ["faq"]},
                                                    {"turn": start + 1, "intents": ["financial"]}])
    blocks = store.get_archived_blocks("s1")
    assert [[e["turn"] for e in b["turn_intents"]] for b in blocks] == [[1, 2], [3, 4]]
    assert blocks[0]["raw_messages"] == messages_to_dict(messages)


class _FailingDurable(repository.InMemoryConversationStore):
    def save_state(self, session_id, state):
        raise RuntimeError("database down")


class _Cache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl_seconds):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


def test_a_failed_database_write_leaves_the_cache_untouched(monkeypatch):
    cache = _Cache()
    monkeypatch.setattr(repository, "cache", cache)
    store = repository.CachedConversationStore(_FailingDurable())
    with pytest.raises(RuntimeError):
        store.save_state("s1", ConversationState(user_id="u1", turn_count=1,
                                                 raw_tail=[HumanMessage("q"), AIMessage("a")]))
    assert cache.values == {}
