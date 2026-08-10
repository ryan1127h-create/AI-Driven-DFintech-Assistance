"""HTTP request/response models for the chatbot module (see
app/modules/chatbot/api.py)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    # Must be a valid UUID (or omitted to start a new session) — it's used
    # directly as student.conversations.conversation_id (see
    # app/modules/chatbot/repository.py), which is a uuid column. Typing
    # this as UUID rejects malformed ids with a clear 422 here, instead of
    # a cryptic Postgres error surfacing as a 500 later.
    session_id: Optional[UUID] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    agent_used: str
