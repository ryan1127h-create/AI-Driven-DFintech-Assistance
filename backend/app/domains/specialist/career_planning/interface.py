"""
Public interface of the career_planning domain — the only module other
domains (and the orchestrator) are allowed to import from
app.domains.specialist.career_planning. Everything else in this package
is private.

The caller assembles one CareerPlanningInput (the student's evidence and
situation, the role catalogue, the course-to-role links); this domain
reads no data itself.

Usage:
    from app.domains.specialist.career_planning.interface import plan_career

    result = plan_career(complete_upstream_agent_report)
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from app.core.logging import get_logger
from app.domains.specialist.career_planning import workflow
from app.domains.specialist.career_planning.contracts import CareerPlanningInput
from app.domains.specialist.career_planning.errors import ErrorCode, input_validation_error
from app.domains.specialist.career_planning.schemas import response_from_result

logger = get_logger(__name__)

__all__ = ["CareerPlanningInput", "plan_career"]


def plan_career(request: CareerPlanningInput | dict) -> dict:
    """Validate the report and run the workflow; the result as plain JSON
    data (dates as ISO strings). Raises CareerPlanningStageError."""
    try:
        validated = CareerPlanningInput.model_validate(request)
    except PydanticValidationError as exc:
        request_id = request.get("request_id", "unknown") if isinstance(request, dict) else "unknown"
        logger.warning("career planning input validation failed request_id=%s code=%s errors=%s",
                       request_id, ErrorCode.INPUT_INVALID, exc.errors())
        raise input_validation_error(request_id=request_id, errors=exc.errors()) from exc
    return response_from_result(workflow.plan_career(validated)).model_dump(mode="json")
