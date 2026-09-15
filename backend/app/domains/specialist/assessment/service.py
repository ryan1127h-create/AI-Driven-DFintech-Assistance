"""
Orchestration for the Application Readiness Assessment: broad retrieval
(no topic filter, so both admission requirements and programme overview are
available) plus the domain's one LLM step (see assessment_agent.py).
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.interface import build_context, cited_sources, retrieve
from app.domains.specialist.assessment import assessment_agent
from app.domains.specialist.assessment.assessment_agent import OnEvent


def assess(
    user_message: str, chat_history: list[dict], on_event: OnEvent | None = None,
) -> tuple[str, list[str]]:
    """Runs the assessment for an applicant who has already shared their
    background (see interface.py — the caller is responsible for deciding
    whether there's enough to assess at all). Returns (answer_text,
    cited_sources)."""
    # Broad retrieval (top_k=5) so both admissions requirements and
    # programme overview are available — no topic filter.
    hits = retrieve(user_message, top_k=5)
    context = build_context(hits) if hits else (
        "No specific programme information is currently available. "
        "Please refer to the official NUS website for accurate details."
    )
    text = assessment_agent.write_assessment(context, chat_history, on_event=on_event)
    return text, cited_sources(hits)
