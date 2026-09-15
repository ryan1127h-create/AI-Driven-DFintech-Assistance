"""
Knowledge QA tool adapter — builds the four chatbot-facing Tools
(admissions/academic/financial/faq) backed by
app.domains.specialist.knowledge_qa. This file is purely wiring: extract
what the domain needs from TurnState (the latest human message, the chat
history as plain role/content dicts), call the domain, wrap the result in
a ToolAnswer — no prompt text and no LLM call live here anymore, both
moved into the domain (see app/domains/specialist/knowledge_qa/qa_agent.py
and service.py).
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import interface as knowledge_qa
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages


def make_knowledge_qa_tool(name: str, topic: str, agent_name: str, trigger_intents: set[str]) -> Tool:
    """Builds a Tool whose handler is a plain knowledge-base Q&A answer
    scoped to one of knowledge_qa's four fixed topics."""

    def handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
        user_message = last_human_message(state.messages)
        chat_history = to_chat_messages(state.messages)
        text, sources = knowledge_qa.answer_topic(topic, user_message, chat_history, on_event=on_event)
        return ToolAnswer(text=text, sources=sources, agent_used=agent_name)

    return Tool(
        name=name,
        description=f"Plain knowledge-base Q&A — {topic}.",
        input_model=ChatToolInput,
        handler=handler,
        trigger_intents=frozenset(trigger_intents),
    )


# ── The four plain-RAG specialists ──────────────────────────────────────────

ADMISSIONS_TOOL = make_knowledge_qa_tool("admissions", "admissions", "admissions_agent", {"admissions"})
ACADEMIC_TOOL = make_knowledge_qa_tool("academic", "academic", "academic_agent", {"academic"})
FINANCIAL_TOOL = make_knowledge_qa_tool("financial", "financial", "financial_agent", {"financial"})
FAQ_TOOL = make_knowledge_qa_tool("faq", "faq", "faq_agent", {"faq"})
