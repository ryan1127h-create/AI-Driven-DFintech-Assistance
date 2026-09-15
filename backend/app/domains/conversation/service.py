"""
Conversation service — everything about a conversation beyond raw storage:
ownership-checked state access, turn recording, block-based incremental
history summarization, locking, and the read-side operations (listing, full
transcript, rollback) the /chat/* endpoints need. Built on top of
repository.py's ConversationStore. Private to the conversation domain —
other domains and the orchestrator should go through interface.py.

Block-freezing is split into two halves, on purpose, to avoid a concurrency
hole: multiple background freeze tasks for the same session could otherwise
each independently decide "this block needs freezing" off a stale read,
redoing the work and racing on whose state update survived. So:
  - should_freeze() is a cheap, synchronous, side-effect-free check — called
    from the orchestrator right after a turn completes, *before* the
    response is sent, together with try_lock(session_id, "summarizing") to
    atomically claim the right to freeze.
  - freeze_and_unlock() does the slow part (one LLM call to summarize) and
    is what actually runs as a FastAPI BackgroundTask, but only for the one
    caller that won the lock — so it never adds latency to the turn that
    triggers it, and never races with another freeze of the same session.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, messages_from_dict

from app.adapters.deepseek_adapter import llm
from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.domains.conversation.models import ConversationState, HistoryBlock
from app.domains.conversation.repository import get_session_store

_SUMMARY_PROMPT = """\
Summarize the following portion of a conversation between a prospective \
student and an NUS MSc DFinTech admissions assistant, in 2-4 concise \
sentences. Focus on what topics were discussed and any preferences, facts, \
or context the user mentioned that could matter later in the conversation. \
Write the summary in English regardless of the conversation's language. Be \
factual — do not add commentary or advice of your own.

Respond with ONLY the summary text, no preamble."""


# ---- session lifecycle / per-turn state -----------------------------------

def new_session_id() -> str:
    return str(uuid.uuid4())


def get_state(session_id: str, user_id: str) -> ConversationState:
    """Loads a session's state and claims/validates ownership: a
    freshly-loaded session with no owner yet (state.user_id is None) is
    claimed by `user_id`. An existing session owned by someone else raises
    ForbiddenError before any LLM/DB work happens."""
    state = get_session_store().get_state(session_id)
    if state.user_id is not None and state.user_id != user_id:
        raise ForbiddenError("This conversation belongs to a different user.")
    state.user_id = user_id
    return state


def record_turn(
    session_id: str, state: ConversationState,
    human_message: HumanMessage, ai_message: AIMessage,
    intents: list[str], agent_used: str,
) -> None:
    """Appends this turn's messages to the raw tail, bumps turn_count, logs
    the intent-classification result, and persists — the state mutation
    every /chat turn ends with, once dispatch has produced an answer."""
    state.turn_count += 1
    state.raw_tail = state.raw_tail + [human_message, ai_message]
    # Intent-classification log for this turn — persisted to the hot
    # conversations table, not the archive, until a future freeze moves the
    # entries covering this turn into the archive.
    state.pending_turn_intents = state.pending_turn_intents + [
        {"turn": state.turn_count, "intents": intents, "agent_used": agent_used}
    ]
    get_session_store().save_state(session_id, state)


def delete_conversation(session_id: str, user_id: str) -> None:
    """Deletes a session's state and archive (cascade FK). Idempotent: a
    session_id nothing was ever saved under is a no-op. Raises
    ForbiddenError if the session belongs to a different authenticated
    user."""
    store = get_session_store()
    state = store.get_state(session_id)
    if state.user_id is not None and state.user_id != user_id:
        raise ForbiddenError("This conversation belongs to a different user.")
    store.delete(session_id)


# ---- locking ----------------------------------------------------------

def try_lock(session_id: str, status: str, user_id: str) -> str | None:
    return get_session_store().try_lock(session_id, status, user_id)


def release_lock(session_id: str) -> None:
    get_session_store().release_lock(session_id)


# ---- block-based incremental history summarization ------------------------

def summarize_block(messages: list[BaseMessage]) -> str:
    """One LLM call, permanent once computed — a block is only ever
    summarized from its raw source, never from a previous summary, so
    repeated compression drift can't accumulate. Never raises (falls back
    to a generic placeholder so a transient failure doesn't crash the
    background task or silently drop the block)."""
    try:
        transcript = "\n".join(
            f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
            for m in messages
        )
        # max_tokens is generous relative to the desired 2-4 sentence
        # summary as a safety margin against truncation.
        return llm.complete(_SUMMARY_PROMPT, transcript, temperature=0, max_tokens=1000).strip()
    except Exception as exc:
        print(f"[conversation.service] Warning: summarize_block failed — {exc}")
        return "(summary unavailable for this portion of the conversation)"


def render_summaries(blocks: list[HistoryBlock]) -> str:
    """Renders frozen block summaries into a compact text block for the LLM
    prompt. Empty list -> empty string (caller should skip injecting a
    SystemMessage entirely in that case)."""
    if not blocks:
        return ""
    lines = [f"- (turns {b.start_turn}-{b.end_turn}) {b.summary}" for b in blocks]
    return "Summary of earlier parts of this conversation:\n" + "\n".join(lines)


def should_freeze(state: ConversationState) -> bool:
    """Pure, side-effect-free check: would the *next* turn push the raw tail
    over settings.history_raw_tail_max? Called synchronously so the freeze
    lock can be claimed before the response is sent — freezing the oldest
    settings.history_block_size turns then happens in the background via
    freeze_and_unlock(), so the summary is already available by the time
    it's next needed."""
    next_tail_turns = (state.turn_count + 1) - state.last_frozen_end
    if next_tail_turns <= settings.history_raw_tail_max:
        return False
    n_msgs = 2 * settings.history_block_size  # strict Human/AI pairing assumed
    return len(state.raw_tail) >= n_msgs


def freeze_and_unlock(session_id: str) -> None:
    """Background-task entry point — runs only for the one caller that
    already won the freeze lock via try_lock(session_id, "summarizing").
    Does the slow part (one LLM call to summarize), archives the block (raw
    messages plus this block's slice of pending_turn_intents — this is the
    only place the archive table ever gets written), and always releases
    the lock via unlock_after_freeze() — including on failure, so a crashed
    or errored attempt can't wedge the session past
    settings.freeze_lock_ttl_seconds. Never raises."""
    store = get_session_store()
    try:
        state = store.get_state(session_id)
    except Exception as exc:
        print(f"[conversation.service] Warning: freeze_and_unlock failed to read state — {exc}")
        return  # nothing safe to write back; the TTL will recover the lock

    try:
        block_size = settings.history_block_size
        n_msgs = 2 * block_size
        if len(state.raw_tail) >= n_msgs:
            block_messages = state.raw_tail[:n_msgs]
            start_turn = state.last_frozen_end + 1
            end_turn = state.last_frozen_end + block_size
            summary = summarize_block(block_messages)
            block = HistoryBlock(
                start_turn=start_turn, end_turn=end_turn, summary=summary,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            # Split off this block's pending intent-log entries (by turn
            # number, not by list position/count, since pending_turn_intents
            # and raw_tail don't necessarily grow in lockstep) — these move
            # into the archive table alongside the block; anything for a
            # later turn stays pending for the next freeze.
            block_intents = [
                e for e in state.pending_turn_intents if start_turn <= e["turn"] <= end_turn
            ]
            remaining_intents = [
                e for e in state.pending_turn_intents if e["turn"] > end_turn
            ]

            store.archive_block(session_id, block, block_messages, block_intents)

            state.last_frozen_end = end_turn
            state.raw_tail = state.raw_tail[n_msgs:]
            state.history_summaries = state.history_summaries + [block]
            state.pending_turn_intents = remaining_intents
    except Exception as exc:
        print(f"[conversation.service] Warning: freeze_and_unlock failed — {exc}")
    finally:
        try:
            store.unlock_after_freeze(session_id, state)
        except Exception as exc:
            print(f"[conversation.service] Warning: freeze_and_unlock failed to unlock — {exc}")


# ---- read-side: listing, full transcript, rollback -------------------------

def _check_conversation(state: ConversationState, session_id: str, user_id: str) -> None:
    """Shared existence/ownership check for the read/rollback operations
    below. A session that was never created shows up from get_state() as a
    fresh default ConversationState (user_id=None, turn_count=0) — that
    combination is the only reliable "doesn't exist" signal, since a
    session can legitimately have turn_count==0 with a real user_id
    already set (a lock claimed via try_lock() before the first turn
    finished). Raises NotFoundError (-> 404) or ForbiddenError (-> 403,
    same as get_state())."""
    if state.user_id is None and state.turn_count == 0:
        raise NotFoundError(f"No conversation found for session_id={session_id}.")
    if state.user_id is not None and state.user_id != user_id:
        raise ForbiddenError("This conversation belongs to a different user.")


def list_conversations(user_id: str) -> list[dict]:
    """All of `user_id`'s conversations, most recently active first — see
    ConversationStore.list_sessions() for the exact shape. Backends with no
    per-user index (redis) return an empty list rather than raising."""
    return get_session_store().list_sessions(user_id)


def _pair_to_turns(
    messages: list[BaseMessage], start_turn: int, archived: bool,
    turn_intents: list[dict] | None = None,
) -> list[dict]:
    """Splits a flat list of alternating Human/AI messages into per-turn
    {"turn", "role", "content", "archived"} entries, two per turn — relies
    on the same strict Human/AI pairing every turn already assumes
    elsewhere in this module (record_turn() above appends exactly one of
    each per turn).

    `turn_intents`, when given, is one of the two {"turn","intents",
    "agent_used"} lists this module already tracks per turn (either an
    archived block's own slice of turn_intents, or the live
    ConversationState.pending_turn_intents — see get_conversation_history()
    below) — looked up by turn number and attached to that turn's "ai"
    entry as `intents`/`agent_used`. A turn with no matching entry (e.g.
    conversations started before this field existed) simply gets neither
    key, so callers should treat their absence as "unknown", not "empty"."""
    by_turn = {entry["turn"]: entry for entry in (turn_intents or [])}

    turns: list[dict] = []
    turn = start_turn
    for i in range(0, len(messages) - 1, 2):
        human, ai = messages[i], messages[i + 1]
        turns.append({"turn": turn, "role": "human", "content": human.content, "archived": archived})
        ai_turn = {"turn": turn, "role": "ai", "content": ai.content, "archived": archived}
        entry = by_turn.get(turn)
        if entry is not None:
            ai_turn["intents"] = entry.get("intents")
            ai_turn["agent_used"] = entry.get("agent_used")
        turns.append(ai_turn)
        turn += 1
    return turns


def get_conversation_history(session_id: str, user_id: str) -> dict:
    """Full turn-by-turn transcript for one conversation: archived blocks
    (real original text) followed by the still-unarchived raw tail, in
    turn order. Raises NotFoundError/ForbiddenError — see
    _check_conversation()."""
    store = get_session_store()
    state = store.get_state(session_id)
    _check_conversation(state, session_id, user_id)

    # De-duplicate by (start_turn, end_turn): archive_block()'s own
    # docstring documents that two concurrent freeze decisions can each
    # archive the same block, so the same turn range can legitimately
    # appear more than once in archived_blocks — first occurrence wins
    # (their content is identical by construction, same source raw_tail).
    seen_ranges: set[tuple[int, int]] = set()
    turns: list[dict] = []
    for block in sorted(store.get_archived_blocks(session_id), key=lambda b: b["start_turn"]):
        block_range = (block["start_turn"], block["end_turn"])
        if block_range in seen_ranges:
            continue
        seen_ranges.add(block_range)
        block_messages = messages_from_dict(block["raw_messages"])
        turns.extend(_pair_to_turns(
            block_messages, block["start_turn"], archived=True,
            turn_intents=block.get("turn_intents"),
        ))
    turns.extend(_pair_to_turns(
        state.raw_tail, state.last_frozen_end + 1, archived=False,
        turn_intents=state.pending_turn_intents,
    ))

    return {
        "session_id": session_id,
        "turn_count": state.turn_count,
        "archived_turn_count": state.last_frozen_end,
        "turns": turns,
        "summaries": [asdict(b) for b in state.history_summaries],
    }


def rollback_conversation(session_id: str, turns_to_remove: int, user_id: str) -> ConversationState:
    """Deletes the most recent `turns_to_remove` turns from the session's
    raw tail (never-archived content only — see module docstring for why
    archived turns can't be touched). Raises NotFoundError/ForbiddenError —
    see _check_conversation() — or ValidationError if `turns_to_remove`
    exceeds how many turns are actually available to roll back."""
    store = get_session_store()
    state = store.get_state(session_id)
    _check_conversation(state, session_id, user_id)

    available = state.turn_count - state.last_frozen_end
    if turns_to_remove > available:
        raise ValidationError(
            f"Can only roll back up to {available} not-yet-archived turn(s); "
            f"requested {turns_to_remove}."
        )

    state.turn_count -= turns_to_remove
    state.raw_tail = state.raw_tail[: len(state.raw_tail) - 2 * turns_to_remove]
    # Drop the now-rolled-back turns' pending intent-log entries too, so
    # they never get archived on a later freeze — these turns no longer
    # exist as far as the conversation goes.
    state.pending_turn_intents = [
        e for e in state.pending_turn_intents if e["turn"] <= state.turn_count
    ]
    store.save_state(session_id, state)
    return state
