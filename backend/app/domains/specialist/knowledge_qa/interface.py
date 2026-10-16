"""
Public interface of the knowledge_qa domain — the only module other
domains (and the orchestrator/tools layer) are allowed to import from
app.domains.specialist.knowledge_qa. Everything else in this package
(qa_agent, facts, guardrail, service internals) is private.

Current consumers:
    - app/tools/specialist/knowledge_qa_tool.py adapts answer_topic() into
      the four chatbot-facing Tools (admissions/academic/financial/faq).

The caller reads the data and passes it in; this domain reads none
itself: the search query to retrieve with (search_query()), the topics to
boost (retrieval_scope()), the retrieved reference context, and the
programme's current facts (current_facts() formats the catalogue's MSc
DFT record).

Usage:
    from app.domains.specialist.knowledge_qa import interface as knowledge_qa
    query = knowledge_qa.search_query(user_message, chat_history)
    text = knowledge_qa.answer_topic("admissions", user_message, chat_history,
                                     context=context, facts=knowledge_qa.current_facts(dft))
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import facts as _facts
from app.domains.specialist.knowledge_qa import qa_agent, service
from app.domains.specialist.knowledge_qa.qa_agent import OnEvent

__all__ = ["answer_topic", "current_facts", "fact_source_urls", "retrieval_scope", "search_query"]


def retrieval_scope(topic: str) -> set[str]:
    """Topics to boost when retrieving context for one of the four fixed
    topics: "admissions", "academic", "financial", "faq"."""
    return service.retrieval_scope(topic)


def search_query(user_message: str, chat_history: list[dict]) -> str:
    """The query to retrieve with: the message, or a standalone English
    rewrite of it when it follows earlier turns or isn't in English."""
    return qa_agent.search_query(user_message, chat_history)


def current_facts(program: dict) -> str:
    """The current key facts block for a programme_catalog programme record
    (the target programme, MSc DFT)."""
    return _facts.current_facts(program)


def fact_source_urls(program: dict) -> list[str]:
    """The official pages current_facts() draws on, for the reply's sources."""
    return _facts.source_urls(program)


def answer_topic(
    topic: str, user_message: str, chat_history: list[dict],
    *, context: str | None, facts: str | None = None, on_event: OnEvent | None = None,
    depth: str | None = None,
) -> str:
    """Knowledge-base Q&A for one of the four fixed topics, grounded in the
    current `facts` block and the caller's retrieved `context`; `depth` is
    the user's answer-detail preference. Returns the answer text (checked:
    figures it cites come from the facts or the context)."""
    return service.answer_topic(
        topic, user_message, chat_history,
        context=context, facts=facts, on_event=on_event, depth=depth,
    )
