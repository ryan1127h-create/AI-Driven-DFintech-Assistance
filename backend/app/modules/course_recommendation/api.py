from fastapi import APIRouter, HTTPException

from app.modules.course_recommendation import service
from app.modules.course_recommendation.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResponse,
    RecommendedCourse,
)

router = APIRouter()


# Deliberately a sync `def` (not `async def`): the service does blocking
# psycopg + LLM calls, and FastAPI runs sync path operations in a threadpool
# so the event loop stays free.
@router.post("/course-recommendations", response_model=CourseRecommendationResponse)
def recommend_courses(request: CourseRecommendationRequest) -> CourseRecommendationResponse:
    """
    Structured course recommendation for the current (placeholder) user.
    Course selection and ranking are fully deterministic (see
    agents/rule_engine.py); the LLM only phrases the per-course reasons and
    degrades to rule-based reasons if unavailable (stated in `notes`).
    """
    try:
        result = service.recommend_courses(
            target_role=request.target_role,
            completed_courses=request.completed_courses,
            preferences=request.preferences,
        )
    except Exception as exc:
        # Full detail stays server-side; clients get a generic message so
        # connection strings/provider errors never leak into responses.
        print(f"[course_recommendation.api] Error: recommendation failed — {exc!r}")
        raise HTTPException(
            status_code=500, detail="Failed to generate course recommendations."
        ) from exc

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
