"""
Conversation history repository — pure data access (no LLM calls). See
app/modules/chatbot/conversation_service.py for the summarization business
logic built on top of this.

Storage shape per session, backed by the `student` schema sandbox (see
app/modules/profile/schema/student_schema_clone.sql for the base tables,
app/modules/chatbot/schema/student_conversations_alter.sql for the
block-summary columns added on top, and
app/modules/chatbot/schema/student_messages_restructure.sql for turning
`messages` into a one-row-per-conversation archive):
  - `student.conversations` (hot table, always small): turn_count,
    last_frozen_end, raw_tail (unfrozen recent messages only),
    history_summaries (list of frozen block summaries). Read/written every
    turn. `conversation_id` doubles as the app-level `session_id`.
  - `student.messages` (cold table, one row per conversation, keyed by the
    same conversation_id): archived_blocks is a jsonb array that each freeze
    appends one entry to — never read on the per-turn hot path, kept for
    audit.

Three backends are available, selected via settings.session_store_backend:
  "memory"          — process-local dict. Lost on restart, not shared across workers.
  "redis"           — the whole ConversationState cached in Redis (no durable backing).
  "supabase_cached" — durable storage in the `student` schema sandbox, with
                       Redis in front as a cache-aside layer. Requires
                       CONVERSATION_DATABASE_URL to be set.

Usage:
    from app.modules.chatbot.repository import get_session_store
    store = get_session_store()
    state = store.get_state(session_id)
    store.save_state(session_id, updated_state)
    store.delete(session_id)
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone

from langchain_core.messages import messages_from_dict, messages_to_dict

from app.clients.postgres_client import LazyPostgresConnection
from app.clients.redis_client import get_redis_client
from app.core.config import settings
from app.modules.chatbot.models import ConversationState, HistoryBlock, state_from_json, state_to_json
from app.modules.profile.interface import TEST_USER_ID

_KEY_PREFIX = "chat:session:"


class ConversationStore(ABC):
    @abstractmethod
    def get_state(self, session_id: str) -> ConversationState:
        ...

    @abstractmethod
    def save_state(self, session_id: str, state: ConversationState) -> None:
        ...

    @abstractmethod
    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list) -> None:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...

    @abstractmethod
    def is_locked(self, session_id: str) -> bool:
        """Whether this session is currently mid-freeze and new chat turns
        should be rejected (see app/modules/chatbot/conversation_service.py
        and app/modules/chatbot/api.py). A lock older than
        settings.freeze_lock_ttl_seconds is treated as stale (crashed/hung
        background task) and reported as unlocked."""
        ...

    @abstractmethod
    def try_lock_for_freeze(self, session_id: str) -> bool:
        """Atomically claims the freeze lock for this session. Returns True
        if the caller now owns it (and should proceed to freeze in a
        background task), False if someone else already holds a live lock."""
        ...

    @abstractmethod
    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        """Persists the post-freeze state and releases the lock, in one
        operation. Callers must call this even on failure (with the
        unchanged state) so a session never stays wedged past the TTL."""
        ...


class InMemoryConversationStore(ConversationStore):
    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._archives: dict[str, list[dict]] = {}
        self._locks: dict[str, float] = {}  # session_id -> lock-acquired time.time()

    def get_state(self, session_id: str) -> ConversationState:
        return self._states.get(session_id, ConversationState())

    def save_state(self, session_id: str, state: ConversationState) -> None:
        self._states[session_id] = state

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list) -> None:
        self._archives.setdefault(session_id, []).append({
            "block": asdict(block), "raw_messages": messages_to_dict(raw_messages),
        })

    def delete(self, session_id: str) -> None:
        self._states.pop(session_id, None)
        self._archives.pop(session_id, None)
        self._locks.pop(session_id, None)

    def is_locked(self, session_id: str) -> bool:
        acquired_at = self._locks.get(session_id)
        if acquired_at is None:
            return False
        return time.time() - acquired_at <= settings.freeze_lock_ttl_seconds

    def try_lock_for_freeze(self, session_id: str) -> bool:
        if self.is_locked(session_id):
            return False
        self._locks[session_id] = time.time()
        return True

    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        self._states[session_id] = state
        self._locks.pop(session_id, None)


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
        return state_from_json(json.loads(raw))

    def save_state(self, session_id: str, state: ConversationState) -> None:
        payload = json.dumps(state_to_json(state))
        self._client.set(self._key(session_id), payload, ex=settings.session_ttl_seconds)

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list) -> None:
        pass  # redis-only backend has no durable archive; state itself already holds summaries

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))

    def _lock_key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}:lock"

    def is_locked(self, session_id: str) -> bool:
        return bool(self._client.exists(self._lock_key(session_id)))

    def try_lock_for_freeze(self, session_id: str) -> bool:
        # SET NX EX is atomic — only one caller can ever win this, and the
        # TTL is Redis-enforced expiry, no separate staleness check needed.
        return bool(self._client.set(
            self._lock_key(session_id), "1", nx=True, ex=settings.freeze_lock_ttl_seconds
        ))

    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        self.save_state(session_id, state)
        self._client.delete(self._lock_key(session_id))


class SupabaseConversationStore(ConversationStore):
    """Durable storage in the `student` schema sandbox (same Supabase project
    as app/modules/profile/repository.py, CONVERSATION_DATABASE_URL) — hot
    `student.conversations` table + cold `student.messages` table (one row
    per conversation in both, `conversation_id` is the PK of each).
    `conversation_id` also doubles as the app-level `session_id` used
    throughout this module — no separate column needed.

    `student.conversations.user_id` is a nullable FK to `student.users`;
    written as app.modules.profile.interface.TEST_USER_ID for consistency
    with the profile module, which operates as the same placeholder identity
    until real auth exists.
    """

    def __init__(self):
        self._conn = LazyPostgresConnection(settings.conversation_database_url)

    def get_state(self, session_id: str) -> ConversationState:
        with self._conn.get().cursor() as cur:
            cur.execute(
                "select turn_count, last_frozen_end, raw_tail, history_summaries "
                "from student.conversations where conversation_id = %s",
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
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into student.conversations
                  (conversation_id, user_id, turn_count, last_frozen_end, raw_tail, history_summaries, total_messages)
                values (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                on conflict (conversation_id) do update
                  set turn_count = excluded.turn_count,
                      last_frozen_end = excluded.last_frozen_end,
                      raw_tail = excluded.raw_tail,
                      history_summaries = excluded.history_summaries,
                      total_messages = excluded.total_messages
                """,
                (
                    session_id, TEST_USER_ID, state.turn_count, state.last_frozen_end,
                    json.dumps(messages_to_dict(state.raw_tail)),
                    json.dumps([asdict(b) for b in state.history_summaries]),
                    2 * state.turn_count,  # strict Human/AI pairing assumed, same as conversation_service.py
                ),
            )
        conn.commit()

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list) -> None:
        """One row per conversation in student.messages (conversation_id is
        its PK), appended to on every freeze rather than inserting new rows
        — this is a single atomic UPDATE using jsonb `||` concatenation, so
        concurrent archive_block calls for the same session serialize
        through Postgres's normal row-level locking instead of each
        inserting their own rows (which is what caused a frozen block to be
        archived 16x over under concurrent load before this change).

        This does NOT protect the separate read-modify-write in save_state()
        (turn_count/last_frozen_end/history_summaries) — two concurrent
        freeze decisions can still each decide to archive the same block, so
        this block's content could still appear twice inside
        archived_blocks. Only the row-count blowup is fixed here."""
        conn = self._conn.get()
        payload = json.dumps([{
            "start_turn": block.start_turn,
            "end_turn": block.end_turn,
            "frozen_at": block.created_at,
            "raw_messages": messages_to_dict(raw_messages),
        }])
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into student.messages (conversation_id, archived_blocks)
                values (%s, %s::jsonb)
                on conflict (conversation_id) do update
                  set archived_blocks = student.messages.archived_blocks || excluded.archived_blocks,
                      updated_at = now()
                """,
                (session_id, payload),
            )
        conn.commit()

    def delete(self, session_id: str) -> None:
        conn = self._conn.get()
        with conn.cursor() as cur:
            # student.messages rows cascade-delete via the FK
            cur.execute("delete from student.conversations where conversation_id = %s", (session_id,))
        conn.commit()

    def is_locked(self, session_id: str) -> bool:
        with self._conn.get().cursor() as cur:
            cur.execute(
                "select status, status_updated_at from student.conversations where conversation_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if not row:
            return False
        status, status_updated_at = row
        if status != "summarizing":
            return False
        age_seconds = (datetime.now(timezone.utc) - status_updated_at).total_seconds()
        return age_seconds <= settings.freeze_lock_ttl_seconds

    def try_lock_for_freeze(self, session_id: str) -> bool:
        """Single atomic CAS: normal->summarizing, or takeover of a stale
        (TTL-expired) lock. rowcount==1 means this caller won it — no
        separate locking needed, Postgres serializes concurrent UPDATEs to
        the same row."""
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                """
                update student.conversations
                set status = 'summarizing', status_updated_at = now()
                where conversation_id = %s
                  and (status = 'normal' or status_updated_at < now() - make_interval(secs => %s))
                """,
                (session_id, settings.freeze_lock_ttl_seconds),
            )
            acquired = cur.rowcount == 1
        conn.commit()
        return acquired

    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                """
                update student.conversations
                set turn_count = %s,
                    last_frozen_end = %s,
                    raw_tail = %s::jsonb,
                    history_summaries = %s::jsonb,
                    total_messages = %s,
                    status = 'normal',
                    status_updated_at = now()
                where conversation_id = %s
                """,
                (
                    state.turn_count, state.last_frozen_end,
                    json.dumps(messages_to_dict(state.raw_tail)),
                    json.dumps([asdict(b) for b in state.history_summaries]),
                    2 * state.turn_count,
                    session_id,
                ),
            )
        conn.commit()


class CachedConversationStore(ConversationStore):
    """Cache-aside wrapper: Redis in front of a durable ConversationStore.

    Caching the whole ConversationState is effective because the state stays
    small forever (bounded raw tail + slowly-growing summaries), instead of a
    blob that grows with total conversation length.
    """

    def __init__(self, durable: ConversationStore):
        self._durable = durable
        self._client = get_redis_client()

    def _key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}"

    def get_state(self, session_id: str) -> ConversationState:
        raw = self._client.get(self._key(session_id))
        if raw:
            return state_from_json(json.loads(raw))

        state = self._durable.get_state(session_id)
        self._client.set(
            self._key(session_id), json.dumps(state_to_json(state)), ex=settings.session_ttl_seconds
        )
        return state

    def save_state(self, session_id: str, state: ConversationState) -> None:
        self._client.set(
            self._key(session_id), json.dumps(state_to_json(state)), ex=settings.session_ttl_seconds
        )
        self._durable.save_state(session_id, state)

    def archive_block(self, session_id: str, block: HistoryBlock, raw_messages: list) -> None:
        self._durable.archive_block(session_id, block, raw_messages)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))
        self._durable.delete(session_id)

    def is_locked(self, session_id: str) -> bool:
        # Never served from cache — lock checks need the live value, not a
        # copy that could be seconds stale.
        return self._durable.is_locked(session_id)

    def try_lock_for_freeze(self, session_id: str) -> bool:
        return self._durable.try_lock_for_freeze(session_id)

    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        self._durable.unlock_after_freeze(session_id, state)
        # Refresh the cache immediately so the next get_state() doesn't read
        # the pre-freeze snapshot until the normal TTL would've expired it.
        self._client.set(
            self._key(session_id), json.dumps(state_to_json(state)), ex=settings.session_ttl_seconds
        )


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
