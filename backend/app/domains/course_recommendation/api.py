from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.responses import Response

from app.core.logging import get_logger
from app.domains.course_recommendation import service
from app.domains.course_recommendation.contracts import CourseRecommendationInput
from app.domains.course_recommendation.errors import input_validation_error
from app.domains.course_recommendation.schemas import (
    CourseRecommendationFailureResponse,
    CourseRecommendationResponse,
    response_from_result,
)

logger = get_logger(__name__)


class _CourseRecommendationRoute(APIRoute):
    """Convert FastAPI body validation into the domain's stage-report format."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original_handler = super().get_route_handler()

        async def stage_aware_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                body = exc.body
                request_id = (
                    body.get("request_id", "unknown")
                    if isinstance(body, dict)
                    else "unknown"
                )
                logger.warning(
                    "course recommendation HTTP input validation failed "
                    "request_id=%s error_count=%s",
                    request_id,
                    len(exc.errors()),
                )
                raise input_validation_error(
                    request_id=request_id,
                    errors=exc.errors(),
                ) from exc

        return stage_aware_handler


router = APIRouter(route_class=_CourseRecommendationRoute)


# Deliberately a sync ``def``: the optional LLM call is blocking, so FastAPI
# runs this operation in a threadpool and keeps the event loop free.
@router.post(
    "/course-recommendations",
    response_model=CourseRecommendationResponse,
    responses={
        422: {
            "model": CourseRecommendationFailureResponse,
            "description": "Input validation failed with stage details.",
        },
        500: {
            "model": CourseRecommendationFailureResponse,
            "description": "A required workflow stage failed.",
        },
        503: {
            "model": CourseRecommendationFailureResponse,
            "description": "A retryable workflow stage failed.",
        },
    },
)
def recommend_courses(
    request: CourseRecommendationInput,
) -> CourseRecommendationResponse:
    """Recommend strictly from the complete report supplied by the upstream agent."""
    result = service.recommend_courses(request)
    return response_from_result(result)
