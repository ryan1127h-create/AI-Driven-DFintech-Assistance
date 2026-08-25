"""
Public interface of the career_planning module — the ONLY file other
modules are allowed to import from app.modules.career_planning.

Current consumers:
    - chatbot's career specialist calls create_career_plan() directly (see
      app/modules/chatbot/agents/specialists/career.py), with a plain-RAG
      fallback only if this call raises.

Usage:
    from app.modules.career_planning.interface import create_career_plan
"""

from __future__ import annotations

from dataclasses import asdict

from app.modules.career_planning import service

__all__ = ["create_career_plan"]


def create_career_plan(
    user_id: str | None = None,
    target_role: str | None = None,
    timeline: str | None = None,
    region: str | None = None,
) -> dict:
    """Runs a career plan and returns it as a plain dict (same shape as the
    /career-plans response body)."""
    result = service.create_career_plan(
        user_id=user_id, target_role=target_role, timeline=timeline, region=region,
    )
    return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(result).items()}
