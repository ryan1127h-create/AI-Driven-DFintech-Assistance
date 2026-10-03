"""
Orchestration for the Application Readiness Assessment: the domain's one
LLM step (see assessment_agent.py) over reference context the caller
retrieved — broadly, with no topic filter, so both admission requirements
and programme overview are available. This domain reads no data itself.
"""

from __future__ import annotations

from app.domains.specialist.assessment import assessment_agent
from app.domains.specialist.assessment.assessment_agent import OnEvent


def assess(
    chat_history: list[dict], *, context: str | None, official_sources: str,
    on_event: OnEvent | None = None, depth: str | None = None,
) -> str:
    """Runs the assessment for an applicant who has already shared their
    background (see interface.py — the caller is responsible for deciding
    whether there's enough to assess at all). Returns the answer text."""
    context = context or (
        "No specific programme information is currently available. "
        "Please refer to the official NUS website for accurate details."
    )
    return assessment_agent.write_assessment(context, official_sources, chat_history, on_event=on_event, depth=depth)
