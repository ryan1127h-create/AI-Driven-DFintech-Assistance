"""
Knowledge QA tool adapter — builds the four chatbot-facing Tools
(admissions/academic/financial/faq) backed by
app.domains.specialist.knowledge_qa. This file is wiring and data access:
extract what the domain needs from TurnState (the latest human message,
the chat history as plain role/content dicts), read the data it answers
from — MSc DFT's checked record in the programme catalogue (the current
intake's fees, dates and requirements) and the knowledge-base passages for
the question — call the domain, and wrap the result in a ToolAnswer. No
prompt text and no LLM call live here (see the domain's qa_agent.py and
service.py).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.domains.program_catalog import interface as program_catalog
from app.domains.specialist.knowledge_qa import interface as knowledge_qa
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.knowledge_context import RetrievedContext, retrieve_context
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages

logger = get_logger(__name__)


def _target_programme() -> dict | None:
    """MSc DFT's catalogue record, or None when the catalogue can't be read
    (the answer then rests on the knowledge base alone)."""
    try:
        return next((p for p in program_catalog.list_programs() if p["is_target"]), None)
    except Exception:
        logger.exception("knowledge qa: reading the programme catalogue failed")
        return None


def make_knowledge_qa_tool(name: str, topic: str, agent_name: str, trigger_intents: set[str]) -> Tool:
    """Builds a Tool whose handler is a knowledge-base Q&A answer scoped to
    one of knowledge_qa's four fixed topics."""

    def handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
        user_message = last_human_message(state.messages)
        chat_history = to_chat_messages(state.messages)
        retrieved = RetrievedContext(text=None)
        if user_message:
            query = knowledge_qa.search_query(user_message, chat_history)
            retrieved = retrieve_context(query, boost_topics=knowledge_qa.retrieval_scope(topic))
        target = _target_programme()
        facts = knowledge_qa.current_facts(target) if target else None
        text = knowledge_qa.answer_topic(
            topic, user_message, chat_history,
            context=retrieved.text, facts=facts, on_event=on_event, depth=state.answer_depth,
            language=state.reply_language,
        )
        fact_sources = knowledge_qa.fact_source_urls(target) if target else []
        sources = list(dict.fromkeys([*retrieved.sources, *fact_sources]))
        return ToolAnswer(text=text, sources=sources, agent_used=agent_name)

    return Tool(
        name=name,
        description=f"Knowledge-base Q&A — {topic}.",
        input_model=ChatToolInput,
        handler=handler,
        trigger_intents=frozenset(trigger_intents),
    )


# ── The four knowledge-base specialists ─────────────────────────────────────

ADMISSIONS_TOOL = make_knowledge_qa_tool("admissions", "admissions", "admissions_agent", {"admissions"})
ACADEMIC_TOOL = make_knowledge_qa_tool("academic", "academic", "academic_agent", {"academic"})
FINANCIAL_TOOL = make_knowledge_qa_tool("financial", "financial", "financial_agent", {"financial"})
FAQ_TOOL = make_knowledge_qa_tool("faq", "faq", "faq_agent", {"faq"})
