"""
Public interface of the program_comparison domain — the only module other
domains (and the orchestrator) are allowed to import from
app.domains.specialist.program_comparison.

The caller supplies every input (knowledge-base chunks, role skills,
applicant facts); this domain reads no data itself.

Usage:
    from app.domains.specialist.program_comparison.interface import compare_programs
"""

from __future__ import annotations

from dataclasses import asdict

from app.domains.specialist.program_comparison import service

__all__ = ["compare_programs"]


def compare_programs(
    chunks: list[dict],
    programs: list[str] | None = None,
    focus: list[str] | None = None,
    target_role: str | None = None,
    role_skills: list[str] | None = None,
    applicant: dict | None = None,
) -> dict:
    """Runs a comparison and returns it as a plain dict. See
    service.compare_programs for the inputs."""
    result = service.compare_programs(
        chunks, programs=programs, focus=focus, target_role=target_role,
        role_skills=role_skills, applicant=applicant,
    )
    return {
        "programs": list(result.programs),
        "comparison_table": [
            {"dimension": dim, "values": result.cells[dim]} for dim in result.dimensions
        ],
        "match_scores": [asdict(m) for m in result.match_scores],
        "program_comments": result.comments,
        "best_fit_summary": result.summary,
        "notes": list(result.notes),
        "sources": list(result.sources),
    }
