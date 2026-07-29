"""
Conversation history store — Phase 6 redesign (block-based incremental
summarization, split hot/cold storage for read efficiency).

Storage shape per session (see app/core/conversation_schema.sql):
  - `conversations` (hot table, always small): turn_count, last_frozen_end,
    raw_tail (unfrozen recent messages only), history_summaries (list of
    frozen block summaries). Read/written every turn.
  - `conversation_archive` (cold table, append-only): full raw messages of
    each frozen block, for audit only — never read on the per-turn hot path.

Three backends are available, selected via settings.session_store_backend:
  "memory"          — process-local dict. Lost on restart, not shared across workers.
  "redis"           — the whole ConversationState cached in Redis (no durable backing).
  "supabase_cached" — durable storage in the conversation Supabase project,
                       with Redis in front as a cache-aside layer. Requires
                       CONVERSATION_DATABASE_URL to be set.

Usage:
    from app.core.session_store import get_session_store
    store = get_session_store()
    state = store.get_state(session_id)
    store.save_state(session_id, updated_state)
    store.delete(session_id)

Block-freezing (the "shrink the raw tail, grow the summaries" step) is
handled by maybe_freeze_block() — meant to run as a FastAPI BackgroundTask
(see app/api/chat.py) so it never adds latency to the turn that triggers it.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import (
    BaseMessage, HumanMessage, SystemMessage,
    messages_from_dict, messages_to_dict,
)

from app.core.config import settings
from app.core.redis_client import get_redis_client

load_dotenv()

_KEY_PREFIX = "chat:session:"


@dataclass
class HistoryBlock:
    start_turn: int
    end_turn: int
    summary: str
    created_at: str


@dataclass
class ConversationState:
    turn_count: int = 0
    last_frozen_end: int = 0
    raw_tail: list[BaseMessage] = field(default_factory=list)
    history_summaries: list[HistoryBlock] = field(default_factory=list)


def _state_to_json(state: ConversationState) -> dict:
    return {
        "turn_count": state.turn_count,
        "last_frozen_end": state.last_frozen_end,
        "raw_tail": messages_to_dict(state.raw_tail),
        "history_summaries": [asdict(b) for b in state.history_summaries],
    }


def _state_from_json(data: dict) -> ConversationState:
    return ConversationState(
        turn_count=data.get("turn_count", 0),
        last_frozen_end=data.get("last_frozen_end", 0),
        raw_tail=messages_from_dict(data.get("raw_tail") or []),
        history_summaries=[HistoryBlock(**b) for b in (data.get("history_summaries") or [])],
    )


# ── Store implementations ───────────────────────────────────────────────────

class ConversationStore(ABC):
    @abstractmethod
    def get_state(self, session_id: str) -> ConversationState:
        ...

    @abstractmethod
    def save_state(self, session_id: str, state: ConversationState) -> None:
        ...

    @abstractmethod
    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list[BaseMessage]) -> None:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...


class InMemoryConversationStore(ConversationStore):
    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._archives: dict[str, list[dict]] = {}

    def get_state(self, session_id: str) -> ConversationState:
        return self._states.get(session_id, ConversationState())

    def save_state(self, session_id: str, state: ConversationState) -> None:
        self._states[session_id] = state

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list[BaseMessage]) -> None:
        self._archives.setdefault(session_id, []).append({
            "block": asdict(block), "raw_messages": messages_to_dict(raw_messages),
        })

    def delete(self, session_id: str) -> None:
        self._states.pop(session_id, None)
        self._archives.pop(session_id, None)


class RedisConversationStore(ConversationStore):
    """Whole ConversationState cached in Redis, no durable backing store."""

    def __init__(self):
        self._client = get_redis_client()

    def _key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}"

    def get_state(self, session_id: str) -> ConversationState:
        raw = self._client.get(self._key(session_id))
        if not raw:
            return ConversationState()
        return _state_from_json(json.loads(raw))

    def save_state(self, session_id: str, state: ConversationState) -> None:
        payload = json.dumps(_state_to_json(state))
        self._client.set(self._key(session_id), payload, ex=settings.session_ttl_seconds)

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list[BaseMessage]) -> None:
        pass  # redis-only backend has no durable archive; state itself already holds summaries

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))


class SupabaseConversationStore(ConversationStore):
    """Durable storage in the conversation Supabase project — hot `conversations`
    table + cold `conversation_archive` table (see app/core/conversation_schema.sql).
    Separate connection from the read-only knowledge base project."""

    def __init__(self):
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(settings.conversation_database_url, connect_timeout=5)
        return self._conn

    def get_state(self, session_id: str) -> ConversationState:
        with self._connection().cursor() as cur:
            cur.execute(
                "select turn_count, last_frozen_end, raw_tail, history_summaries "
                "from conversations where session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if not row:
            return ConversationState()
        turn_count, last_frozen_end, raw_tail, history_summaries = row
        return ConversationState(
            turn_count=turn_count,
            last_frozen_end=last_frozen_end,
            raw_tail=messages_from_dict(raw_tail or []),
            history_summaries=[HistoryBlock(**b) for b in (history_summaries or [])],
        )

    def save_state(self, session_id: str, state: ConversationState) -> None:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into conversations
                  (session_id, turn_count, last_frozen_end, raw_tail, history_summaries, updated_at)
                values (%s, %s, %s, %s::jsonb, %s::jsonb, now())
                on conflict (session_id) do update
                  set turn_count = excluded.turn_count,
                      last_frozen_end = excluded.last_frozen_end,
                      raw_tail = excluded.raw_tail,
                      history_summaries = excluded.history_summaries,
                      updated_at = now()
                """,
                (
                    session_id, state.turn_count, state.last_frozen_end,
                    json.dumps(messages_to_dict(state.raw_tail)),
                    json.dumps([asdict(b) for b in state.history_summaries]),
                ),
            )
        conn.commit()

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list[BaseMessage]) -> None:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into conversation_archive (session_id, start_turn, end_turn, raw_messages)
                values (%s, %s, %s, %s::jsonb)
                """,
                (session_id, block.start_turn, block.end_turn, json.dumps(messages_to_dict(raw_messages))),
            )
        conn.commit()

    def delete(self, session_id: str) -> None:
        conn = self._connection()
        with conn.cursor() as cur:
            # conversation_archive rows cascade-delete via the FK
            cur.execute("delete from conversations where session_id = %s", (session_id,))
        conn.commit()


class CachedConversationStore(ConversationStore):
    """Cache-aside wrapper: Redis in front of a durable ConversationStore.

    Caching the whole ConversationState is now much more effective than in
    Phase 5: the state stays small forever (bounded raw tail + slowly-growing
    summaries), instead of a blob that grows with total conversation length.
    """

    def __init__(self, durable: ConversationStore):
        self._durable = durable
        self._client = get_redis_client()

    def _key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}"

    def get_state(self, session_id: str) -> ConversationState:
        raw = self._client.get(self._key(session_id))
        if raw:
            return _state_from_json(json.loads(raw))

        state = self._durable.get_state(session_id)
        self._client.set(
            self._key(session_id), json.dumps(_state_to_json(state)), ex=settings.session_ttl_seconds
        )
        return state

    def save_state(self, session_id: str, state: ConversationState) -> None:
        self._client.set(
            self._key(session_id), json.dumps(_state_to_json(state)), ex=settings.session_ttl_seconds
        )
        self._durable.save_state(session_id, state)

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list[BaseMessage]) -> None:
        self._durable.archive_block(session_id, block, raw_messages)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))
        self._durable.delete(session_id)


_store: ConversationStore | None = None


def get_session_store() -> ConversationStore:
    """Returns the process-wide conversation store singleton, backend chosen by settings."""
    global _store
    if _store is None:
        backend = settings.session_store_backend
        if backend == "supabase_cached":
            _store = CachedConversationStore(SupabaseConversationStore())
        elif backend == "redis":
            _store = RedisConversationStore()
        else:
            _store = InMemoryConversationStore()
    return _store


# ── Block summarization ─────────────────────────────────────────────────────

_SUMMARY_PROMPT = """\
Summarize the following portion of a conversation between a prospective \
student and an NUS MSc DFinTech admissions assistant, in 2-4 concise \
sentences. Focus on what topics were discussed and any preferences, facts, \
or context the user mentioned that could matter later in the conversation. \
Write the summary in English regardless of the conversation's language. Be \
factual — do not add commentary or advice of your own.

Respond with ONLY the summary text, no preamble."""


def _build_summary_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_tokens=200,
    )


def summarize_block(messages: list[BaseMessage]) -> str:
    """One Groq call, permanent once computed — a block is only ever
    summarized from its raw source, never from a previous summary, so
    repeated compression drift can't accumulate. Never raises (falls back to
    a generic placeholder so a transient failure doesn't crash the
    background task or silently drop the block)."""
    try:
        transcript = "\n".join(
            f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
            for m in messages
        )
        llm = _build_summary_llm()
        response = llm.invoke([
            SystemMessage(content=_SUMMARY_PROMPT),
            HumanMessage(content=transcript),
        ])
        return response.content.strip()
    except Exception as exc:
        print(f"[session_store] Warning: summarize_block failed — {exc}")
        return "(summary unavailable for this portion of the conversation)"


def render_summaries(blocks: list[HistoryBlock]) -> str:
    """Renders frozen block summaries into a compact text block for the LLM
    prompt. Empty list -> empty string (caller should skip injecting a
    SystemMessage entirely in that case)."""
    if not blocks:
        return ""
    lines = [f"- (turns {b.start_turn}-{b.end_turn}) {b.summary}" for b in blocks]
    return "Summary of earlier parts of this conversation:\n" + "\n".join(lines)


def maybe_freeze_block(store: ConversationStore, session_id: str) -> None:
    """Background-task entry point (see app/api/chat.py): checks whether the
    *next* turn would push the raw tail over settings.history_raw_tail_max,
    and if so, freezes the oldest settings.history_block_size turns into a
    permanent summary now — so the summary is already available by the time
    the next turn actually arrives. Never raises."""
    try:
        state = store.get_state(session_id)
        block_size = settings.history_block_size

        next_tail_turns = (state.turn_count + 1) - state.last_frozen_end
        if next_tail_turns <= settings.history_raw_tail_max:
            return

        n_msgs = 2 * block_size  # strict Human/AI pairing assumed
        if len(state.raw_tail) < n_msgs:
            return  # not enough raw messages yet to fill a block (defensive)

        block_messages = state.raw_tail[:n_msgs]
        start_turn = state.last_frozen_end + 1
        end_turn = state.last_frozen_end + block_size
        summary = summarize_block(block_messages)
        block = HistoryBlock(
            start_turn=start_turn, end_turn=end_turn, summary=summary,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        store.archive_block(session_id, block, block_messages)

        state.last_frozen_end = end_turn
        state.raw_tail = state.raw_tail[n_msgs:]
        state.history_summaries = state.history_summaries + [block]
        store.save_state(session_id, state)
    except Exception as exc:
        print(f"[session_store] Warning: maybe_freeze_block failed — {exc}")
