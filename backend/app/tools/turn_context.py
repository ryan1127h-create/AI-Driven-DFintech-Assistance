"""
The context every orchestrator-facing tool (a RAG specialist, the career/
comparison integrations, assessment) receives — built once per turn by the
orchestrator and passed to whichever tool(s) get called. Lives in the
tools layer (not the orchestrator layer) because tools need to import the
type their own handlers accept, and a lower layer can never import from a
higher one — the orchestrator, one layer up, imports this same type rather
than defining its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from app.ports.llm_port import ChatMessage

# Progress/token sink for the streaming chat endpoint — a per-call concern,
# not part of TurnState itself, since the same state is reused across
# several tool invocations within one dispatch, each wanting a different
# value (the sole tool streams to the user; a dispatch branch gets None).
# Passed explicitly to registry.invoke_typed(..., on_event=...); every tool
# must treat a missing/None value as "don't emit anything".
OnEvent = Callable[[dict], None]


@dataclass
class TurnState:
    messages: list[BaseMessage]
    user_id: str
    # Set once by the orchestrator's intent classifier from the latest user
    # message; None/empty when nothing was mentioned. Consumed by the
    # career/comparison tools to avoid a second, dedicated extraction LLM
    # call — the domains behind them already treat "no role/programme
    # given" as a first-class, gracefully-handled case.
    target_role_hint: str | None = None
    program_hints: list[str] = field(default_factory=list)
    # Also set by the intent classifier (see orchestrator/routing.py) — the
    # language the FINAL reply should end up in. Every generation prompt in
    # this app (RAG, assessment, general chat, evaluation) ignores this
    # field entirely and answers in English as usual; only
    # orchestrator/localization.py reads it, as the very last step of a
    # turn. "en" (the default) means "no conversion needed".
    reply_language: str = "en"


class ChatToolInput(BaseModel):
    """The Tool contract requires a pydantic input_model per registration,
    even though the orchestrator always calls these tools via
    registry.invoke_typed() with an actual TurnState (never parsed through
    this model at runtime) — this class exists purely so each registration
    still documents its real input shape."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[BaseMessage]
    user_id: str
    target_role_hint: str | None = None
    program_hints: list[str] = Field(default_factory=list)
    reply_language: str = "en"


def last_human_message(messages: list[BaseMessage]) -> str:
    """Returns the latest user message's text, or "" if none is present.
    Shared by every tool that needs "what did the user just ask"."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def to_chat_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
    """Converts langchain message objects to the plain role/content pairs
    LLMPort.stream() takes — the port boundary is where langchain's message
    types stop, so a provider swap never has to touch this conversion."""
    result: list[ChatMessage] = []
    for m in messages:
        role = "assistant" if isinstance(m, AIMessage) else "user"
        content = m.content if isinstance(m.content, str) else str(m.content)
        result.append({"role": role, "content": content})
    return result
