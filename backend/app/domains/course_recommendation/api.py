from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.course_recommendation import service
from app.domains.course_recommendation.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResponse,
    RecommendedCourse,
)

router = APIRouter()


# Deliberately a sync `def` (not `async def`): the service does blocking
# psycopg + LLM calls, and FastAPI runs sync path operations in a threadpool
# so the event loop stays free.
@router.post("/course-recommendations", response_model=CourseRecommendationResponse)
def recommend_courses(
    request: CourseRecommendationRequest,
    user_id: str = Depends(get_current_user_id),
) -> CourseRecommendationResponse:
    """
    Structured course recommendation for the current authenticated user.
    Course selection and ranking are fully deterministic (see
    rule_engine.py); the LLM only phrases the per-course reasons and
    degrades to rule-based reasons if unavailable (stated in `notes`).
    """
    result = service.recommend_courses(
        user_id=user_id,
        target_role=request.target_role,
        completed_courses=request.completed_courses,
        preferences=request.preferences,
    )

    return CourseRecommendationResponse(
        target_role=result.target_role,
        recommended_courses=[RecommendedCourse(**r) for r in result.recommendations],
        skill_gaps=list(result.skill_gaps),
        completed_recognized=list(result.completed_recognized),
        completed_unrecognized=list(result.completed_unrecognized),
        completed_units=result.completed_units,
        notes=list(result.notes),
        sources=list(result.sources),
    )
