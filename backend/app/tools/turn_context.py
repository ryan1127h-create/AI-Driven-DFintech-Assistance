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

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.ports.llm_port import ChatMessage

# Progress/token sink for the streaming chat endpoint — a per-call concern,
# not part of TurnState itself, since the same state is reused across
# several tool invocations within one dispatch, each wanting a different
# value (the sole tool streams to the user; a dispatch branch gets None).
# Passed explicitly to registry.invoke_typed(..., on_event=...); every tool
# must treat a missing/None value as "don't emit anything".
OnEvent = Callable[[dict], None]


@dataclass(frozen=True)
class PreviousTurn:
    """The conversation's last completed turn, for reading the current
    message in its light: a short reply like "software engineering" or
    "the second one" usually answers what the assistant just asked."""

    user_message: str
    reply: str
    intents: tuple[str, ...] = ()
    agent_used: str = ""
    # The tools' structured record of what they did (ToolAnswer.contexts).
    contexts: tuple[dict, ...] = ()

    def context_for(self, tool: str) -> dict | None:
        return next((c for c in self.contexts if c.get("tool") == tool), None)

    @property
    def awaiting(self) -> dict | None:
        """The question the reply ended on, if a tool recorded one."""
        return next((c["awaiting"] for c in self.contexts if c.get("awaiting")), None)

    def reply_tail(self, chars: int = 300) -> str:
        """The reply's ending — where its closing question usually is."""
        text = self.reply.strip()
        return text if len(text) <= chars else "…" + text[-chars:]


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
    # Also from the intent classifier: for a course recommendation, which
    # kind of advice is wanted — "degree_overview", "ad_hoc" or
    # "semester_plan" (see classification.COURSE_MODES); None otherwise.
    course_mode_hint: str | None = None
    # Likewise for career advice: "exploration", "plan" or "compare" (see
    # classification.CAREER_MODES); None otherwise.
    career_mode_hint: str | None = None
    # Likewise for a programme comparison: "compare", "detail" or "explore"
    # (see classification.COMPARISON_MODES); None otherwise.
    comparison_mode_hint: str | None = None
    # Input fields the user skipped or dismissed earlier in this
    # conversation (see orchestrator/dispatch/requirements.py): an optional
    # or supplementary field here isn't asked for again this session.
    declined_fields: frozenset[str] = frozenset()
    # Also set by the intent classifier (see orchestrator/classification.py)
    # (resolved by turn_service) — the language the reply is written in.
    # The tools that write the final text pass it to their generation
    # prompts (app/core/reply_language.py); orchestrator/dispatch/
    # localization.py converts a finished reply only if it is still in
    # another language (fixed English replies, the assessment).
    reply_language: str = "en"
    # The user's answer-detail preference (concise / standard / detailed,
    # see app/core/answer_depth.py), read from their settings once per
    # turn. Like reply_language it is applied while answers are written,
    # by every tool that writes the final text.
    answer_depth: str = "standard"
    # The conversation's last completed turn (None on a new conversation),
    # loaded by turn_service from the conversation state.
    previous_turn: PreviousTurn | None = None
    # The other tools answering this same message in a multi-tool turn
    # (set per branch by orchestrator/dispatch/execution.py; empty when the
    # tool answers alone). Their replies are joined, so a tool answering
    # from the whole message (knowledge Q&A) keeps to its own part.
    other_tools: tuple[str, ...] = ()


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
        # Context the orchestrator places ahead of the turns (the profile,
        # earlier-turn summaries) stays a system message — sent as "user",
        # the model would read it as something the user said.
        role = "assistant" if isinstance(m, AIMessage) else "system" if isinstance(m, SystemMessage) else "user"
        content = m.content if isinstance(m.content, str) else str(m.content)
        result.append({"role": role, "content": content})
    return result
