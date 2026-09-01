"""HTTP request/response models for the orchestrator (see api.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # Must be a valid UUID (or omitted to start a new session) — it's used
    # directly as the conversation's primary key, a uuid column. Typing
    # this as UUID rejects malformed ids with a clear 422 here, instead of
    # a cryptic Postgres error surfacing as a 500 later.
    session_id: Optional[UUID] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    agent_used: str


class ConversationSummary(BaseModel):
    session_id: str
    turn_count: int
    last_frozen_end: int
    updated_at: Optional[datetime] = None
    preview: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationTurn(BaseModel):
    turn: int
    role: Literal["human", "ai"]
    content: str
    # True if this turn came from the archive (frozen, permanent) rather
    # than the still-mutable raw tail.
    archived: bool
    # Only set on "ai" turns, and only when this turn's intent-classification
    # log entry is still available — None for a turn from before this field
    # existed, not for "no intent". Never set on "human" turns.
    intents: Optional[list[str]] = None
    agent_used: Optional[str] = None


class HistoryBlockOut(BaseModel):
    start_turn: int
    end_turn: int
    summary: str
    created_at: str


class ConversationHistoryResponse(BaseModel):
    session_id: str
    turn_count: int
    # How many of the leading turns are permanently archived (and therefore
    # not roll-backable, see RollbackRequest below).
    archived_turn_count: int
    turns: list[ConversationTurn]
    summaries: list[HistoryBlockOut]


class RollbackRequest(BaseModel):
    # How many of the most recent turns to delete. Must be <= turn_count -
    # archived_turn_count (see ConversationHistoryResponse) — the endpoint
    # rejects anything larger rather than silently clamping it.
    turns: int = Field(..., ge=1)


class RollbackResponse(BaseModel):
    session_id: str
    turn_count: int
    archived_turn_count: int
    removed_turns: int
