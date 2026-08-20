"""
Chat service — orchestrates one conversational turn: loads conversation
state + applicant profile, builds the prompt, runs the LangGraph supervisor,
and persists the updated state. This is the "engine" behind the /chat
endpoint (see app/modules/chatbot/api.py), kept independent of FastAPI so it
stays easy to test or reuse from another entry point.

Profile data is read-only here — this module never writes to the profile
module's storage, and only ever reaches it through
app.modules.profile.interface (never its repository/models directly), per
the module-isolation rule: cross-module data only flows through a module's
public interface.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, messages_from_dict

from app.modules.chatbot.agents.supervisor import supervisor_graph
from app.modules.chatbot.conversation_service import render_summaries
from app.modules.chatbot.models import ConversationState
from app.modules.chatbot.repository import get_session_store
from app.modules.profile.interface import get_profile_summary_text


@dataclass
class ChatTurnResult:
    session_id: str
    reply: str
    agent_used: str
    user_message: str
    intents: list[str] = field(default_factory=list)


def run_turn(session_id: str | None, message: str, user_id: str) -> ChatTurnResult:
    """
    - Creates a new session_id if one is not provided.
    - Loads conversation state: a bounded raw tail + any frozen block
      summaries (see app/modules/chatbot/repository.py). This is never a
      full-history read: the row itself stays small regardless of how long
      the conversation has run.
    - Ownership: a freshly-loaded session with no owner yet (state.user_id
      is None — either brand new, or predates auth) is claimed by `user_id`.
      An existing session owned by someone else raises PermissionError
      before any LLM/DB work happens — see app/modules/chatbot/api.py for
      how that's turned into a 403.
    - Reads the applicant's profile (read-only — see module docstring) for
      the profile-summary system message (this already includes lifecycle
      stage when known — see profile.interface.get_profile_summary_text).
    - Prepends the profile summary and the history-block summaries, then
      the raw tail, then the new message.
    - Runs the LangGraph supervisor.
    - Persists the updated state (raw tail grows by one turn).

    The caller (see app/modules/chatbot/api.py) is responsible for
    scheduling the post-turn background task (block-freezing) — that needs
    FastAPI's BackgroundTasks, which this function deliberately knows
    nothing about. There is no profile-update background task any more:
    the profile is populated only via the resume-upload endpoint (see
    app/modules/profile/api.py), never from conversation turns.
    """
    session_id = session_id or str(uuid.uuid4())
    store = get_session_store()
    state = store.get_state(session_id)

    if state.user_id is not None and state.user_id != user_id:
        raise PermissionError("This conversation belongs to a different user.")
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

    result = supervisor_graph.invoke({
        "messages": llm_messages,
        "agent_used": "",
        "reply": "",
        "user_id": user_id,
        "target_role_hint": None,
        "program_hints": [],
    })

    # result["messages"] is llm_messages plus whatever the graph appended
    # (exactly one AI message) — slice by position rather than equality,
    # since two messages could coincidentally match content.
    new_ai_messages = result["messages"][len(llm_messages):]

    state.turn_count += 1
    state.raw_tail = state.raw_tail + [new_message] + new_ai_messages
    store.save_state(session_id, state)

    # Best-effort observability: never let a logging failure break a chat
    # turn that otherwise succeeded (same discipline as summarize_block() /
    # retrieve() elsewhere in this module's neighborhood).
    try:
        store.log_turn(session_id, state.turn_count, result.get("intents", []), result["agent_used"])
    except Exception as exc:
        print(f"[chatbot.service] Warning: log_turn failed — {exc}")

    return ChatTurnResult(
        session_id=session_id,
        reply=result["reply"],
        agent_used=result["agent_used"],
        user_message=message,
        intents=result.get("intents", []),
    )


def _check_conversation(state, session_id: str, user_id: str) -> None:
    """Shared existence/ownership check for the read/rollback endpoints
    below. A session that was never created shows up from get_state() as a
    fresh default ConversationState (user_id=None, turn_count=0) — that
    combination is the only reliable "doesn't exist" signal, since a session
    can legitimately have turn_count==0 with a real user_id already set (a
    lock claimed via try_lock() before the first turn finished). Raises
    LookupError (-> 404) or PermissionError (-> 403, same as run_turn())."""
    if state.user_id is None and state.turn_count == 0:
        raise LookupError(f"No conversation found for session_id={session_id}.")
    if state.user_id is not None and state.user_id != user_id:
        raise PermissionError("This conversation belongs to a different user.")


def list_conversations(user_id: str) -> list[dict]:
    """All of `user_id`'s conversations, most recently active first — see
    ConversationStore.list_sessions() for the exact shape. Backends with no
    per-user index (redis) return an empty list rather than raising."""
    return get_session_store().list_sessions(user_id)


def _pair_to_turns(messages: list[BaseMessage], start_turn: int, archived: bool) -> list[dict]:
    """Splits a flat list of alternating Human/AI messages into per-turn
    {"turn", "role", "content", "archived"} entries, two per turn — relies
    on the same strict Human/AI pairing every turn already assumes
    elsewhere in this module (run_turn() above appends exactly one of each
    per turn, see its own comment on new_ai_messages)."""
    turns: list[dict] = []
    turn = start_turn
    for i in range(0, len(messages) - 1, 2):
        human, ai = messages[i], messages[i + 1]
        turns.append({"turn": turn, "role": "human", "content": human.content, "archived": archived})
        turns.append({"turn": turn, "role": "ai", "content": ai.content, "archived": archived})
        turn += 1
    return turns


def get_conversation_history(session_id: str, user_id: str) -> dict:
    """Full turn-by-turn transcript for one conversation: archived blocks
    (from student.messages, real original text — see
    repository.py::get_archived_blocks) followed by the still-unarchived
    raw tail, in turn order. Raises LookupError/PermissionError — see
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
        turns.extend(_pair_to_turns(block_messages, block["start_turn"], archived=True))
    turns.extend(_pair_to_turns(state.raw_tail, state.last_frozen_end + 1, archived=False))

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
        raise ValueError(
            f"Can only roll back up to {available} not-yet-archived turn(s); "
            f"requested {turns_to_remove}."
        )

    state.turn_count -= turns_to_remove
    state.raw_tail = state.raw_tail[: len(state.raw_tail) - 2 * turns_to_remove]
    store.save_state(session_id, state)
    return state
