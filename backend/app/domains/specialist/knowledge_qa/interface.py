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

The caller retrieves the reference context (retrieval_scope() says how
for a fixed topic) and passes it in; this domain reads no data itself.

Usage:
    from app.domains.specialist.knowledge_qa import interface as knowledge_qa
    text = knowledge_qa.answer_topic("admissions", user_message, chat_history,
                                     context=context, official_sources=sources_text)
"""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import service
from app.domains.specialist.knowledge_qa.qa_agent import OnEvent

__all__ = ["answer_topic", "answer_with_role_prompt", "retrieval_scope"]


def retrieval_scope(topic: str) -> set[str]:
    """Topics to boost when retrieving context for one of the four fixed
    topics: "admissions", "academic", "financial", "faq"."""
    return service.retrieval_scope(topic)


def answer_topic(
    topic: str, user_message: str, chat_history: list[dict],
    *, context: str | None, official_sources: str, on_event: OnEvent | None = None,
    depth: str | None = None,
) -> str:
    """Knowledge-base Q&A for one of the four fixed topics, grounded in the
    caller's retrieved `context`; `depth` is the user's answer-detail
    preference. Returns the answer text."""
    return service.answer_topic(
        topic, user_message, chat_history,
        context=context, official_sources=official_sources, on_event=on_event, depth=depth,
    )


def answer_with_role_prompt(
    role_prompt: str, user_message: str, chat_history: list[dict],
    *, context: str | None, on_event: OnEvent | None = None, depth: str | None = None,
) -> str:
    """Same generation as answer_topic(), for a caller with its own role
    prompt instead of one of the four fixed topics."""
    return service.answer_with_role_prompt(
        role_prompt, user_message, chat_history, context=context, on_event=on_event, depth=depth,
    )
