"""Shared LangGraph state definition for the supervisor graph and every
specialist node (see app/modules/chatbot/agents/supervisor.py)."""

from __future__ import annotations

import operator
from typing import Annotated, Callable, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    agent_used: str
    reply: str
    intents: List[str]  # 1-3 of: admissions | academic | financial | career |
                         # comparison | faq | assessment | general
    user_id: str
    # Set once by classify_intent_node from the latest user message; None/empty
    # when nothing was mentioned. Consumed by career_node/comparison_node (see
    # agents/specialists/career.py, agents/specialists/comparison.py) to avoid
    # a second, dedicated extraction LLM call — the downstream modules
    # (course_recommendation, program_comparison) already treat "no role/
    # programme given" as a first-class, gracefully-handled case.
    target_role_hint: str | None
    program_hints: List[str]
    # Optional progress/token sink for the streaming chat endpoint (see
    # app/modules/chatbot/api.py's POST /chat/stream and service.py::run_turn).
    # None on the plain (non-streaming) /chat path — every node that reads
    # this must treat a missing/None value as "don't emit anything", so the
    # existing /chat endpoint's behavior is completely unaffected. There's no
    # checkpointer configured on supervisor_graph, so storing a plain
    # (non-JSON-serializable) callable in state is safe here.
    on_event: Optional[Callable[[dict], None]]


def last_human_message(messages: list[BaseMessage]) -> str:
    """Returns the latest user message's text, or "" if none is present.
    Shared by every node that needs "what did the user just ask" — the
    supervisor's intent classifier and dispatch fan-out, every RAG agent,
    and the assessment agent."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""
