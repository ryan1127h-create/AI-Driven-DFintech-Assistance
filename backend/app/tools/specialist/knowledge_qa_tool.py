"""
Knowledge QA tool adapter — builds the four chatbot-facing Tools
(admissions/academic/financial/faq) backed by
app.domains.specialist.knowledge_qa. This file is wiring and data access:
extract what the domain needs from TurnState (the latest human message,
the chat history as plain role/content dicts), read the data it answers
from — MSc DFT's current facts (app/tools/programme_facts.py) and the
knowledge-base passages for the question — call the domain, and wrap the
result in a ToolAnswer. No prompt text and no LLM call live here (see the
domain's qa_agent.py and service.py).

The answers skip the orchestrator's draft evaluation: the domain checks
every figure and date it cites against what it was given, and says so
plainly when the material doesn't cover a question.
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import interface as knowledge_qa
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.knowledge_context import RetrievedContext, retrieve_context
from app.tools.programme_facts import current_facts
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages


def make_knowledge_qa_tool(name: str, topic: str, agent_name: str, trigger_intents: set[str]) -> Tool:
    """Builds a Tool whose handler is a knowledge-base Q&A answer scoped to
    one of knowledge_qa's four fixed topics."""

    def handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
        user_message = last_human_message(state.messages)
        chat_history = to_chat_messages(state.messages)
        retrieved = RetrievedContext(text=None)
        if user_message:
            query = knowledge_qa.search_query(user_message, chat_history)
            if state.stage_search_hints.get(name):
                query = f"{query} {state.stage_search_hints[name]}"
            retrieved = retrieve_context(query, boost_topics=knowledge_qa.retrieval_scope(topic))
        facts = current_facts()
        text = knowledge_qa.answer_topic(
            topic, user_message, chat_history,
            context=retrieved.text, facts=facts.text, on_event=on_event, depth=state.answer_depth,
            language=state.reply_language, other_tools=state.other_tools,
            stage_note=state.stage_notes.get(name),
        )
        sources = list(dict.fromkeys([*retrieved.sources, *facts.sources]))
        # Pointing to the official pages instead of answering is a fallback.
        used = f"{agent_name}_fallback" if knowledge_qa.is_unverified(text) else agent_name
        return ToolAnswer(text=text, sources=sources, agent_used=used)

    return Tool(
        name=name,
        description=f"Knowledge-base Q&A — {topic}.",
        input_model=ChatToolInput,
        handler=handler,
        trigger_intents=frozenset(trigger_intents),
        skip_evaluation=True,
    )


# ── The four knowledge-base specialists ─────────────────────────────────────

ADMISSIONS_TOOL = make_knowledge_qa_tool("admissions", "admissions", "admissions_agent", {"admissions"})
ACADEMIC_TOOL = make_knowledge_qa_tool("academic", "academic", "academic_agent", {"academic"})
FINANCIAL_TOOL = make_knowledge_qa_tool("financial", "financial", "financial_agent", {"financial"})
FAQ_TOOL = make_knowledge_qa_tool("faq", "faq", "faq_agent", {"faq"})
