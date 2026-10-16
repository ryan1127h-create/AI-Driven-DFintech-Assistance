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
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from app.core.logging import get_logger
from app.domains.specialist.program_comparison import workflow
from app.domains.specialist.program_comparison.contracts import ComparisonInput
from app.domains.specialist.program_comparison.errors import ErrorCode, input_validation_error
from app.domains.specialist.program_comparison.schemas import response_from_result

logger = get_logger(__name__)

__all__ = ["ComparisonInput", "compare"]


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

