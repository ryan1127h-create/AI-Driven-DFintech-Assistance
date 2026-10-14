"""
Public interface of the program_comparison domain — the only module other
domains (and the orchestrator) are allowed to import from
app.domains.specialist.program_comparison. Everything else in this package
is private.

The caller assembles one ComparisonInput (the verified programme
catalogue with MSc DFT as the baseline, the applicant, what was asked);
this domain reads no data itself.

Usage:
    from app.domains.specialist.program_comparison.interface import compare

    result = compare(complete_upstream_agent_report)

compare_programs() is the previous comparison path, still used by the
comparison tool until it moves to compare().
"""

from __future__ import annotations

from dataclasses import asdict

from pydantic import ValidationError as PydanticValidationError

from app.core.logging import get_logger
from app.domains.specialist.program_comparison import service, workflow
from app.domains.specialist.program_comparison.contracts import ComparisonInput
from app.domains.specialist.program_comparison.errors import ErrorCode, input_validation_error
from app.domains.specialist.program_comparison.schemas import response_from_result

logger = get_logger(__name__)

__all__ = ["ComparisonInput", "compare", "compare_programs"]


def compare(request: ComparisonInput | dict) -> dict:
    """Validate the report and run the workflow; the result as plain JSON
    data (dates as ISO strings). Raises ProgramComparisonStageError."""
    try:
        validated = ComparisonInput.model_validate(request)
    except PydanticValidationError as exc:
        request_id = request.get("request_id", "unknown") if isinstance(request, dict) else "unknown"
        logger.warning("programme comparison input validation failed request_id=%s code=%s errors=%s",
                       request_id, ErrorCode.INPUT_INVALID, exc.errors())
        raise input_validation_error(request_id=request_id, errors=exc.errors()) from exc
    return response_from_result(workflow.compare(validated))


def compare_programs(
    chunks: list[dict],
    programs: list[str] | None = None,
    focus: list[str] | None = None,
    target_role: str | None = None,
    role_skills: list[str] | None = None,
    applicant: dict | None = None,
) -> dict:
    """The previous comparison over knowledge-base chunks, as a plain dict."""
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
