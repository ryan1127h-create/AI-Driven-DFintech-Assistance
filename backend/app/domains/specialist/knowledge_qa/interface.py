"""
Public interface of the knowledge_qa domain — the only module other
domains (and the orchestrator/tools layer) are allowed to import from
app.domains.specialist.knowledge_qa. Everything else in this package
(qa_agent, service internals) is private.

Current consumers:
    - app/tools/specialist/knowledge_qa_tool.py adapts answer_topic() into
      the four chatbot-facing Tools (admissions/academic/financial/faq).
    - app/tools/specialist/program_comparison_tool.py's legacy-RAG
      fallback uses answer_with_role_prompt() with its own
      comparison-specific prompt.

Usage:
    from app.domains.specialist.knowledge_qa import interface as knowledge_qa
    text, sources = knowledge_qa.answer_topic("admissions", user_message, chat_history)
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import service
from app.domains.specialist.knowledge_qa.qa_agent import OnEvent

__all__ = ["answer_topic", "answer_with_role_prompt"]


def answer_topic(
    topic: str, user_message: str, chat_history: list[dict],
    on_event: OnEvent | None = None,
) -> tuple[str, list[str]]:
    """Plain knowledge-base Q&A for one of the four fixed topics:
    "admissions", "academic", "financial", "faq". Returns (answer_text,
    cited_sources)."""
    return service.answer_topic(topic, user_message, chat_history, on_event=on_event)


def answer_with_role_prompt(
    role_prompt: str, user_message: str, chat_history: list[dict],
    on_event: OnEvent | None = None, *, filter_topics: set[str] | None = None,
) -> tuple[str, list[str]]:
    """Same RAG mechanism as answer_topic(), for a caller with its own role
    prompt and topic scoping instead of one of the four fixed topics."""
    return service.answer_with_role_prompt(
        role_prompt, user_message, chat_history,
        on_event=on_event, filter_topics=filter_topics,
    )
