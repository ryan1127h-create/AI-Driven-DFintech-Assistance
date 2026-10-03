"""
Public interface of the career_planning domain — the only module other
domains (and the orchestrator) are allowed to import from
app.domains.specialist.career_planning.

The caller resolves the target role and supplies the user's career
evidence and the retrieved reference chunks; this domain reads no data
itself.

Usage:
    from app.domains.specialist.career_planning.interface import create_career_plan
"""

from __future__ import annotations

from dataclasses import asdict

from app.domains.specialist.career_planning import service

__all__ = ["create_career_plan"]


def create_career_plan(
    target_role: str | None,
    profile_evidence: list[str],
    reference_chunks: list[dict],
    sources: list[str],
    timeline: str | None = None,
    region: str | None = None,
) -> dict:
    """Runs a career plan and returns it as a plain dict. See
    service.create_career_plan for the inputs."""
    result = service.create_career_plan(
        target_role, profile_evidence, reference_chunks, sources, timeline=timeline, region=region,
    )
    return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(result).items()}
