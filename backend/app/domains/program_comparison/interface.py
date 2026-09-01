"""
Public interface of the program_comparison domain — the only module other
domains (and the orchestrator) are allowed to import from
app.domains.program_comparison.

Usage:
    from app.domains.program_comparison.interface import compare_programs
"""

from __future__ import annotations

from dataclasses import asdict

from app.domains.program_comparison import service

__all__ = ["compare_programs"]


def compare_programs(
    user_id: str | None = None,
    programs: list[str] | None = None,
    focus: list[str] | None = None,
    target_role: str | None = None,
) -> dict:
    """Runs a comparison and returns it as a plain dict (same shape as the
    /program-comparisons response body)."""
    result = service.compare_programs(
        user_id=user_id, programs=programs, focus=focus, target_role=target_role,
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
