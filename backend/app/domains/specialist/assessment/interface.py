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

The caller retrieves the reference context (broadly, no topic filter)
and passes it in; this domain reads no data itself.

Usage:
    from app.domains.specialist.assessment.interface import assess
    text = assess(chat_history, context=context, official_sources=sources_text)
"""

from __future__ import annotations

from app.domains.specialist.assessment import service
from app.domains.specialist.assessment.assessment_agent import OnEvent

__all__ = ["assess"]


def assess(
    chat_history: list[dict], *, context: str | None, official_sources: str,
    on_event: OnEvent | None = None, depth: str | None = None,
) -> str:
    """Runs the Application Readiness Assessment: one LLM generation call
    against the 9-section structured prompt, grounded in `context`.
    Returns the answer text."""
    return service.assess(chat_history, context=context, official_sources=official_sources, on_event=on_event, depth=depth)
