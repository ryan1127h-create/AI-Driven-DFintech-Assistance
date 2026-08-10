"""
Conversation domain models — block-based incremental history summarization
state (see app/modules/chatbot/conversation_service.py and
app/modules/chatbot/repository.py).
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


def state_to_json(state: ConversationState) -> dict:
    return {
        "turn_count": state.turn_count,
        "last_frozen_end": state.last_frozen_end,
        "raw_tail": messages_to_dict(state.raw_tail),
        "history_summaries": [asdict(b) for b in state.history_summaries],
    }


def state_from_json(data: dict) -> ConversationState:
    return ConversationState(
        turn_count=data.get("turn_count", 0),
        last_frozen_end=data.get("last_frozen_end", 0),
        raw_tail=messages_from_dict(data.get("raw_tail") or []),
        history_summaries=[HistoryBlock(**b) for b in (data.get("history_summaries") or [])],
    )
