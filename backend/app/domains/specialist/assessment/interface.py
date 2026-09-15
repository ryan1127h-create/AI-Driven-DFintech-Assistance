"""
Public interface of the assessment domain — the only module other domains
(and the tools layer) are allowed to import from
app.domains.specialist.assessment. Everything else in this package
(assessment_agent, service internals) is private.

Current consumers:
    - app/tools/specialist/assessment_tool.py adapts assess() into the
      chatbot-facing ASSESSMENT_TOOL. The "is there enough to assess at
      all" check (needs_clarification) lives in that adapter, not here —
      this domain always assumes a real user_message was given.

Usage:
    from app.domains.specialist.assessment.interface import assess
    text, sources = assess(user_message, chat_history)
"""

from __future__ import annotations

from app.domains.specialist.assessment import service
from app.domains.specialist.assessment.assessment_agent import OnEvent

__all__ = ["assess"]


def assess(
    user_message: str, chat_history: list[dict], on_event: OnEvent | None = None,
) -> tuple[str, list[str]]:
    """Runs the Application Readiness Assessment: broad knowledge-base
    retrieval (no topic filter) plus one LLM generation call against the
    9-section structured prompt. Returns (answer_text, cited_sources)."""
    return service.assess(user_message, chat_history, on_event=on_event)
