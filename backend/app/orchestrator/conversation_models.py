"""
Conversation domain models — block-based incremental history summarization
state (see conversation_service.py and conversation_repository.py).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict


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
    # One {"turn": int, "intents": list[str], "agent_used": str} entry per
    # turn since the last freeze — the intent-classification log for
    # not-yet-archived turns. Lives here (not in the archive table) so that
    # every turn writes only to the hot conversations table;
    # freeze_and_unlock() (see conversation_service.py) moves the entries
    # covered by a frozen block into the archive and drops them from here.
    pending_turn_intents: list[dict] = field(default_factory=list)
    # Owning user, set the first time a session is used and checked against
    # the caller's authenticated user_id on every subsequent turn (see
    # turn_service.py::run_turn) — None only for a session that hasn't been
    # used yet.
    user_id: str | None = None


def state_to_json(state: ConversationState) -> dict:
    return {
        "turn_count": state.turn_count,
        "last_frozen_end": state.last_frozen_end,
        "raw_tail": messages_to_dict(state.raw_tail),
        "history_summaries": [asdict(b) for b in state.history_summaries],
        "pending_turn_intents": state.pending_turn_intents,
        "user_id": state.user_id,
    }


def state_from_json(data: dict) -> ConversationState:
    return ConversationState(
        turn_count=data.get("turn_count", 0),
        last_frozen_end=data.get("last_frozen_end", 0),
        raw_tail=messages_from_dict(data.get("raw_tail") or []),
        history_summaries=[HistoryBlock(**b) for b in (data.get("history_summaries") or [])],
        pending_turn_intents=data.get("pending_turn_intents") or [],
        user_id=data.get("user_id"),
    )
