"""
Turn service — orchestrates one conversational turn: loads conversation
state + applicant profile, classifies intent, dispatches to the matched
tool(s), and persists the updated state. This is the "engine" behind the
/chat endpoint (see api.py), kept independent of FastAPI so it stays easy
to test or reuse from another entry point.

Profile data is read-only here — this module never writes to the profile
domain's storage, and only ever reaches it through profile.interface
(never its repository/models directly), per the module-isolation rule:
cross-domain data only flows through a domain's public interface.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, messages_from_dict

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.domains.profile.interface import get_profile_summary_text
from app.orchestrator import dispatch, routing
from app.orchestrator.conversation_models import ConversationState
from app.orchestrator.conversation_repository import get_session_store
from app.orchestrator.conversation_service import render_summaries
from app.tools.turn_context import OnEvent, TurnState


@dataclass
class ChatTurnResult:
    session_id: str
    reply: str
    agent_used: str
    user_message: str
    intents: list[str] = field(default_factory=list)


def run_turn(
    session_id: str | None, message: str, user_id: str,
    on_event: OnEvent | None = None,
) -> ChatTurnResult:
    """
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries. This is never a full-history read: the row itself stays
      small regardless of how long the conversation has run.
    - Ownership: a freshly-loaded session with no owner yet (state.user_id
      is None) is claimed by `user_id`. An existing session owned by
      someone else raises PermissionError before any LLM/DB work happens.
    - Reads the applicant's profile (read-only) for the profile-summary
      system message (this already includes lifecycle stage when known).
    - Prepends the profile summary and the history-block summaries, then
      the raw tail, then the new message.
    - Classifies intent, then dispatches to the matched tool(s).
    - Persists the updated state (raw tail grows by one turn).

    The caller (see api.py) is responsible for scheduling the post-turn
    background task (block-freezing) — that needs FastAPI's
    BackgroundTasks, which this function deliberately knows nothing about.

    `on_event`, when given, is forwarded into routing/dispatch to report
    progress ("step") and answer-text ("token") events for the streaming
    endpoint. Every tool treats a missing/None value as "emit nothing", so
    leaving this at its default here (the plain /chat endpoint) changes
    nothing about this function's behavior or return value.
    """
    session_id = session_id or str(uuid.uuid4())
    store = get_session_store()
    state = store.get_state(session_id)

    if state.user_id is not None and state.user_id != user_id:
        raise ForbiddenError("This conversation belongs to a different user.")
    state.user_id = user_id

    new_message = HumanMessage(content=message)

    profile_text = get_profile_summary_text(user_id)
    summaries_text = render_summaries(state.history_summaries)

    system_blocks = []
    if profile_text:
        system_blocks.append(SystemMessage(content=profile_text))
    if summaries_text:
        system_blocks.append(SystemMessage(content=summaries_text))

    llm_messages = system_blocks + state.raw_tail + [new_message]

    intents, target_role_hint, program_hints = routing.classify_intent(llm_messages, on_event)
    turn_state = TurnState(
        messages=llm_messages, user_id=user_id,
        target_role_hint=target_role_hint, program_hints=program_hints,
    )
    ai_message, reply, agent_used = dispatch.answer_turn(turn_state, intents, on_event)

    state.turn_count += 1
    state.raw_tail = state.raw_tail + [new_message, ai_message]
    # Intent-classification log for this turn — persisted to the hot
    # conversations table below, not the archive, until a future freeze
    # moves the entries covering this turn into the archive.
    state.pending_turn_intents = state.pending_turn_intents + [
        {"turn": state.turn_count, "intents": intents, "agent_used": agent_used}
    ]
    store.save_state(session_id, state)

    return ChatTurnResult(
        session_id=session_id, reply=reply, agent_used=agent_used,
        user_message=message, intents=intents,
    )


def _check_conversation(state: ConversationState, session_id: str, user_id: str) -> None:
    """Shared existence/ownership check for the read/rollback endpoints
    below. A session that was never created shows up from get_state() as a
    fresh default ConversationState (user_id=None, turn_count=0) — that
    combination is the only reliable "doesn't exist" signal, since a
    session can legitimately have turn_count==0 with a real user_id
    already set (a lock claimed via try_lock() before the first turn
    finished). Raises LookupError (-> 404) or PermissionError (-> 403,
    same as run_turn())."""
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
    elsewhere in this module (run_turn() above appends exactly one of each
    per turn).

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
    turn order. Raises LookupError/PermissionError — see
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
    archived turns can't be touched). Raises LookupError/PermissionError —
    see _check_conversation() — or ValueError if `turns_to_remove` exceeds
    how many turns are actually available to roll back."""
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
