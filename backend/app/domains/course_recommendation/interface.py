"""
Public interface of the course_recommendation domain — the only module
other domains (and the orchestrator) are allowed to import from
app.domains.course_recommendation. Everything else in this package
(rule engine, selection agent, and service internals) is private.

Usage:
    from app.domains.course_recommendation.interface import recommend_courses

    result = recommend_courses(complete_upstream_agent_report)
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from app.core.logging import get_logger
from app.domains.course_recommendation import service
from app.domains.course_recommendation.contracts import CourseRecommendationInput
from app.domains.course_recommendation.errors import (
    ErrorCode,
    input_validation_error,
)
from app.domains.course_recommendation.schemas import response_from_result

logger = get_logger(__name__)

__all__ = [
    "CourseRecommendationInput",
    "recommend_courses",
]


def recommend_courses(
    request: CourseRecommendationInput | dict,
) -> dict:
    """Validate and run the sole upstream-agent report boundary."""
    try:
        validated = CourseRecommendationInput.model_validate(request)
    except PydanticValidationError as exc:
        request_id = (
            request.get("request_id", "unknown")
            if isinstance(request, dict)
            else "unknown"
        )
        logger.warning(
            "course recommendation input validation failed request_id=%s code=%s errors=%s",
            request_id,
            ErrorCode.INPUT_INVALID,
            exc.errors(),
        )
        raise input_validation_error(
            request_id=request_id,
            errors=exc.errors(),
        ) from exc

    result = service.recommend_courses(validated)
    return response_from_result(result).model_dump(mode="json")
