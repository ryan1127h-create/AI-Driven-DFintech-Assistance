"""
Conversation history repository — pure data access (no LLM calls). See
app/modules/chatbot/conversation_service.py for the summarization business
logic built on top of this.

Storage shape per session, backed by the `student` schema sandbox (see
app/modules/profile/schema/student_schema_clone.sql for the base tables,
app/modules/chatbot/schema/student_conversations_alter.sql for the
block-summary columns added on top,
app/modules/chatbot/schema/student_conversations_add_pending_intents.sql for
the pending-intent column described below, and
app/modules/chatbot/schema/student_messages_restructure.sql for turning
`messages` into a one-row-per-conversation archive):
  - `student.conversations` (hot table, always small): turn_count,
    last_frozen_end, raw_tail (unfrozen recent messages only),
    history_summaries (list of frozen block summaries), pending_turn_intents
    (one {"turn","intents","agent_used"} entry per not-yet-archived turn —
    see app/modules/chatbot/models.py::ConversationState). Read/written every
    turn — this is the ONLY table a normal /chat turn writes to.
    `conversation_id` doubles as the app-level `session_id`.
  - `student.messages` (cold table, one row per conversation, keyed by the
    same conversation_id): archived_blocks is a jsonb array that each freeze
    appends one entry to, and turn_intents is the same shape, moved wholesale
    out of `conversations.pending_turn_intents` for exactly the turns that
    block covers. Both columns are written together, in one statement, only
    by archive_block() — this table is never touched by a normal turn, only
    by a history-block freeze (see conversation_service.py::freeze_and_unlock).
    Never read on the per-turn hot path, kept for audit.

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

from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict

from app.clients.postgres_client import LazyPostgresConnection
from app.clients.redis_client import get_redis_client
from app.core.config import settings
from app.modules.chatbot.models import ConversationState, HistoryBlock, state_from_json, state_to_json

_KEY_PREFIX = "chat:session:"
_PREVIEW_MAX_CHARS = 120


def _preview_from_raw_tail(raw_tail: list) -> str:
    """Best-effort one-line preview for list_sessions() — the most recent
    human message in a raw_tail (still in messages_to_dict() form), or ""
    if there isn't one (e.g. a session whose entire raw_tail was just
    frozen away). Never raises: a malformed entry just gets skipped rather
    than breaking the whole session list."""
    try:
        messages = messages_from_dict(raw_tail or [])
    except Exception:
        return ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            text = str(message.content)
            return text[:_PREVIEW_MAX_CHARS] + ("..." if len(text) > _PREVIEW_MAX_CHARS else "")
    return ""


class ConversationStore(ABC):
    @abstractmethod
    def get_state(self, session_id: str) -> ConversationState:
        ...

    @abstractmethod
    def save_state(self, session_id: str, state: ConversationState) -> None:
        ...

    @abstractmethod
    def archive_block(
        self, session_id: str, block: HistoryBlock, raw_messages: list, turn_intents: list[dict]
    ) -> None:
        """Moves one frozen block's raw messages and the pending intent-log
        entries that cover the same turn range into student.messages, in one
        write. `turn_intents` is the slice of ConversationState.
        pending_turn_intents the caller (conversation_service.py::
        freeze_and_unlock) has already selected for this block — this method
        only persists it, it never decides which entries belong here."""
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...

    @abstractmethod
    def try_lock(self, session_id: str, status: str, user_id: str) -> str | None:
        """Atomically attempts to move this session's lock status from
        'normal' (or a stale lock older than settings.freeze_lock_ttl_seconds
        — treated as a crashed/hung holder) to `status`. `user_id` is the
        authenticated caller — only SupabaseConversationStore uses it (to
        stamp ownership on a session_id that doesn't have a row yet; see its
        override), the in-memory/Redis-only backends accept and ignore it.
        Two distinct lock reasons currently exist:
          - "processing": a /chat turn for this session is being handled —
            guards the whole read-modify-write in service.run_turn() so two
            concurrent turns for the same session can no longer silently
            overwrite each other's saved state (see app/modules/chatbot/api.py).
          - "summarizing": a history-block freeze is in progress (see
            app/modules/chatbot/conversation_service.py).
        Returns None if the caller now owns the lock, or the status string
        of whichever lock is currently blocking it otherwise — callers use
        this to report a specific reason (e.g. 409 vs 423) without a second
        round trip."""
        ...

    @abstractmethod
    def release_lock(self, session_id: str) -> None:
        """Releases any lock back to 'normal' without touching persisted
        conversation state. Use unlock_after_freeze() instead when the
        release must be atomic with persisting updated state."""
        ...

    @abstractmethod
    def unlock_after_freeze(self, session_id: str, state: ConversationState) -> None:
        """Persists the post-freeze state and releases the lock, in one
        operation. Callers must call this even on failure (with the
        unchanged state) so a session never stays wedged past the TTL."""
        ...

    @abstractmethod
    def get_archived_blocks(self, session_id: str) -> list[dict]:
        """Reads back every block archive_block() has ever written for this
        session, oldest first, each as a plain dict shaped exactly like the
        arguments archive_block() takes:
        {"start_turn": int, "end_turn": int, "frozen_at": str, "raw_messages": [...], "turn_intents": [...]}
        (raw_messages is still in messages_to_dict() form — callers should
        run it through messages_from_dict() themselves, same as raw_tail).
        Backends with no durable archive (redis) return []."""
        ...

    @abstractmethod
    def list_sessions(self, user_id: str) -> list[dict]:
        """Lists every session owned by `user_id`, most recently active
        first, as plain dicts: {"session_id": str, "turn_count": int,
        "last_frozen_end": int, "updated_at": <timestamp or None>,
        "preview": str}. `preview` is the most recent human message in the
        raw tail, truncated — best-effort, "" if there isn't one. Backends
        with no per-user index (redis) return []."""
        ...


class InMemoryConversationStore(ConversationStore):
    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._archives: dict[str, list[dict]] = {}
        self._locks: dict[str, tuple[str, float]] = {}  # session_id -> (status, acquired time.time())

    def get_state(self, session_id: str) -> ConversationState:
        return self._states.get(session_id, ConversationState())

    def save_state(self, session_id: str, state: ConversationState) -> None:
        self._states[session_id] = state

    def archive_block(
        self, session_id: str, block: HistoryBlock, raw_messages: list, turn_intents: list[dict]
    ) -> None:
        self._archives.setdefault(session_id, []).append({
            "block": asdict(block),
            "raw_messages": messages_to_dict(raw_messages),
            "turn_intents": turn_intents,
        })

    def delete(self, session_id: str) -> None:
        self._states.pop(session_id, None)
        self._archives.pop(session_id, None)
        self._locks.pop(session_id, None)

    def get_archived_blocks(self, session_id: str) -> list[dict]:
        # Flattened to the same {"start_turn","end_turn","frozen_at",
        # "raw_messages","turn_intents"} shape archive_block()'s caller
        # passes in, even though this backend's internal storage nests part
        # of it under "block".
        return [
            {
                **entry["block"],
                "frozen_at": entry["block"]["created_at"],
                "raw_messages": entry["raw_messages"],
                "turn_intents": entry["turn_intents"],
            }
            for entry in self._archives.get(session_id, [])
        ]

    def list_sessions(self, user_id: str) -> list[dict]:
        return [
            {
                "session_id": session_id,
                "turn_count": state.turn_count,
                "last_frozen_end": state.last_frozen_end,
                "updated_at": None,  # this backend doesn't track a timestamp
                "preview": _preview_from_raw_tail(messages_to_dict(state.raw_tail)),
            }
            for session_id, state in self._states.items()
            if state.user_id == user_id
        ]

    def _active_lock_status(self, session_id: str) -> str | None:
        existing = self._locks.get(session_id)
        if existing is None:
            return None
        status, acquired_at = existing
        if time.time() - acquired_at > settings.freeze_lock_ttl_seconds:
            return None  # stale
        return status

    def try_lock(self, session_id: str, status: str, user_id: str) -> str | None:
        blocking = self._active_lock_status(session_id)
        if blocking is not None:
            return blocking
        self._locks[session_id] = (status, time.time())
        return None

    def release_lock(self, session_id: str) -> None:
        self._locks.pop(session_id, None)

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

    def archive_block(
        self, session_id: str, block: HistoryBlock, raw_messages: list, turn_intents: list[dict]
    ) -> None:
        pass  # redis-only backend has no durable archive; state itself already holds summaries

    def get_archived_blocks(self, session_id: str) -> list[dict]:
        return []  # same reasoning as archive_block() above — nothing to read back

    def list_sessions(self, user_id: str) -> list[dict]:
        return []  # no per-user index over Redis keys on this backend

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))

    def _lock_key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}:lock"

    def try_lock(self, session_id: str, status: str, user_id: str) -> str | None:
        # SET NX EX is atomic — only one caller can ever win this, and the
        # TTL is Redis-enforced expiry, no separate staleness check needed.
        # The lock key's value is the status string itself, so a losing
        # caller can read back what's blocking it without a second lookup
        # racing against the lock expiring in between.
        key = self._lock_key(session_id)
        if self._client.set(key, status, nx=True, ex=settings.freeze_lock_ttl_seconds):
            return None
        # "unknown" only if the key expired in the instant between the
        # failed SET and this GET — vanishingly rare, and safe to treat as
        # still-blocked rather than risk reporting a false success.
        return self._client.get(key) or "unknown"

    def release_lock(self, session_id: str) -> None:
        self._client.delete(self._lock_key(session_id))

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
    written as the authenticated caller's user_id (see
    app/modules/auth/interface.py::get_current_user_id), threaded down
    through ConversationState.user_id / try_lock()'s user_id argument.
    """

    def __init__(self):
        self._conn = LazyPostgresConnection(settings.conversation_database_url)

    def get_state(self, session_id: str) -> ConversationState:
        with self._conn.get().cursor() as cur:
            cur.execute(
                "select turn_count, last_frozen_end, raw_tail, history_summaries, "
                "pending_turn_intents, user_id "
                "from student.conversations where conversation_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if not row:
            return ConversationState()
        turn_count, last_frozen_end, raw_tail, history_summaries, pending_turn_intents, user_id = row
        return ConversationState(
            turn_count=turn_count,
            last_frozen_end=last_frozen_end,
            raw_tail=messages_from_dict(raw_tail or []),
            history_summaries=[HistoryBlock(**b) for b in (history_summaries or [])],
            pending_turn_intents=pending_turn_intents or [],
            user_id=str(user_id) if user_id is not None else None,
        )

    def save_state(self, session_id: str, state: ConversationState) -> None:
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into student.conversations
                  (conversation_id, user_id, turn_count, last_frozen_end, raw_tail,
                   history_summaries, pending_turn_intents, total_messages)
                values (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                on conflict (conversation_id) do update
                  set turn_count = excluded.turn_count,
                      last_frozen_end = excluded.last_frozen_end,
                      raw_tail = excluded.raw_tail,
                      history_summaries = excluded.history_summaries,
                      pending_turn_intents = excluded.pending_turn_intents,
                      total_messages = excluded.total_messages
                """,
                (
                    session_id, state.user_id, state.turn_count, state.last_frozen_end,
                    json.dumps(messages_to_dict(state.raw_tail)),
                    json.dumps([asdict(b) for b in state.history_summaries]),
                    json.dumps(state.pending_turn_intents),
                    2 * state.turn_count,  # strict Human/AI pairing assumed, same as conversation_service.py
                ),
            )
        conn.commit()

    def archive_block(
        self, session_id: str, block: HistoryBlock, raw_messages: list, turn_intents: list[dict]
    ) -> None:
        """One row per conversation in student.messages (conversation_id is
        its PK), appended to on every freeze rather than inserting new rows
        — this is a single atomic UPDATE using jsonb `||` concatenation, so
        concurrent archive_block calls for the same session serialize
        through Postgres's normal row-level locking instead of each
        inserting their own rows (which is what caused a frozen block to be
        archived 16x over under concurrent load before this change).

        Writes archived_blocks and turn_intents together in one statement —
        this is the only method that writes to student.messages, and it
        only runs from conversation_service.py::freeze_and_unlock (never on
        a normal turn), so this table is genuinely archive-only:
        `turn_intents` here is just the slice of the caller's
        ConversationState.pending_turn_intents that this block covers, moved
        out of student.conversations and into this table's own copy — the
        caller is responsible for then dropping those entries from
        pending_turn_intents before it next calls save_state()/
        unlock_after_freeze().

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
        intents_payload = json.dumps(turn_intents)
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into student.messages (conversation_id, archived_blocks, turn_intents)
                values (%s, %s::jsonb, %s::jsonb)
                on conflict (conversation_id) do update
                  set archived_blocks = student.messages.archived_blocks || excluded.archived_blocks,
                      turn_intents = student.messages.turn_intents || excluded.turn_intents,
                      updated_at = now()
                """,
                (session_id, payload, intents_payload),
            )
        conn.commit()

    def get_archived_blocks(self, session_id: str) -> list[dict]:
        """Read-only SELECT of student.messages.archived_blocks — the array
        is already in append order (oldest block first) since archive_block()
        only ever grows it via jsonb `||` concatenation, so no further
        sorting is needed here (callers may still sort defensively by
        start_turn if they want to be independent of that guarantee).
        archived_blocks and turn_intents are two parallel arrays — each
        archive_block() call appends exactly one entry to both in the same
        statement, so they zip elementwise by position."""
        with self._conn.get().cursor() as cur:
            cur.execute(
                "select archived_blocks, turn_intents from student.messages where conversation_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return []
        blocks, intents = row[0], (row[1] or [])
        return [
            {**block, "turn_intents": intents[i] if i < len(intents) else []}
            for i, block in enumerate(blocks)
        ]

    def list_sessions(self, user_id: str) -> list[dict]:
        with self._conn.get().cursor() as cur:
            cur.execute(
                "select conversation_id, turn_count, last_frozen_end, status_updated_at, raw_tail "
                "from student.conversations where user_id = %s order by status_updated_at desc",
                (user_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "session_id": str(conversation_id),
                "turn_count": turn_count,
                "last_frozen_end": last_frozen_end,
                "updated_at": status_updated_at,
                "preview": _preview_from_raw_tail(raw_tail or []),
            }
            for conversation_id, turn_count, last_frozen_end, status_updated_at, raw_tail in rows
        ]

    def delete(self, session_id: str) -> None:
        conn = self._conn.get()
        with conn.cursor() as cur:
            # student.messages rows cascade-delete via the FK
            cur.execute("delete from student.conversations where conversation_id = %s", (session_id,))
        conn.commit()

    def try_lock(self, session_id: str, status: str, user_id: str) -> str | None:
        """Atomic CAS: normal->`status`, or takeover of a stale
        (TTL-expired) lock — via upsert, not a plain UPDATE, because a
        client is allowed to supply its own session_id for a brand-new
        conversation (see ChatRequest.session_id), so the row may not exist
        yet. A plain `UPDATE ... WHERE conversation_id = %s` would silently
        match zero rows in that case (rowcount==0, indistinguishable from
        "someone else holds a live lock" without this upsert) — every
        caller for a not-yet-existing session would then wrongly read that
        as "acquired" and race unprotected. `INSERT ... ON CONFLICT DO
        UPDATE ... WHERE` creates the row (already locked, stamped with the
        caller's user_id) on first use, or conditionally updates it same as
        before — an existing row's user_id is intentionally left untouched
        (not part of the `set` clause), so this can't be used to steal
        ownership of someone else's session. `RETURNING` tells us whether
        the DO UPDATE branch's WHERE clause actually matched.

        On failure, looks up the current status to report back to the
        caller (e.g. so api.py can tell "processing" and "summarizing"
        apart with a distinct HTTP status each)."""
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into student.conversations (conversation_id, user_id, status, status_updated_at)
                values (%s, %s, %s, now())
                on conflict (conversation_id) do update
                  set status = excluded.status, status_updated_at = excluded.status_updated_at
                  where student.conversations.status = 'normal'
                     or student.conversations.status_updated_at < now() - make_interval(secs => %s)
                returning conversation_id
                """,
                (session_id, user_id, status, settings.freeze_lock_ttl_seconds),
            )
            acquired = cur.fetchone() is not None
        conn.commit()
        if acquired:
            return None

        with conn.cursor() as cur:
            cur.execute(
                "select status from student.conversations where conversation_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def release_lock(self, session_id: str) -> None:
        conn = self._conn.get()
        with conn.cursor() as cur:
            cur.execute(
                "update student.conversations set status = 'normal', status_updated_at = now() "
                "where conversation_id = %s",
                (session_id,),
            )
        conn.commit()

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
                    pending_turn_intents = %s::jsonb,
                    total_messages = %s,
                    status = 'normal',
                    status_updated_at = now()
                where conversation_id = %s
                """,
                (
                    state.turn_count, state.last_frozen_end,
                    json.dumps(messages_to_dict(state.raw_tail)),
                    json.dumps([asdict(b) for b in state.history_summaries]),
                    json.dumps(state.pending_turn_intents),
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

    def archive_block(
        self, session_id: str, block: HistoryBlock, raw_messages: list, turn_intents: list[dict]
    ) -> None:
        # Write-only, rarely-read archive — no caching benefit.
        self._durable.archive_block(session_id, block, raw_messages, turn_intents)

    def get_archived_blocks(self, session_id: str) -> list[dict]:
        # Not cached — this read path is only hit when a user opens an old
        # conversation's history, not on every turn, so there's no
        # meaningful benefit to caching it (same reasoning as archive_block()
        # above).
        return self._durable.get_archived_blocks(session_id)

    def list_sessions(self, user_id: str) -> list[dict]:
        # Same reasoning as get_archived_blocks() above — no per-user cache.
        return self._durable.list_sessions(user_id)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._key(session_id))
        self._durable.delete(session_id)

    def try_lock(self, session_id: str, status: str, user_id: str) -> str | None:
        # Never served from cache — lock checks need the live value, not a
        # copy that could be seconds stale.
        return self._durable.try_lock(session_id, status, user_id)

    def release_lock(self, session_id: str) -> None:
        self._durable.release_lock(session_id)

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
