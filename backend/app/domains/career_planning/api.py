from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.career_planning import service
from app.domains.career_planning.schemas import CareerPlanRequest, CareerPlanResponse, PlannedCourse

router = APIRouter()


# Sync `def` on purpose: the service does blocking DB + LLM calls, and
# FastAPI runs sync path operations in a threadpool.
@router.post("/career-plans", response_model=CareerPlanResponse)
def create_career_plan(
    request: CareerPlanRequest,
    user_id: str = Depends(get_current_user_id),
) -> CareerPlanResponse:
    """
    Personal career plan for the current authenticated user. Skill gaps and
    course picks come from the course_recommendation domain; the LLM only
    writes the narrative, with a deterministic fallback (stated in `notes`).
    """
    result = service.create_career_plan(
        user_id=user_id,
        target_role=request.target_role,
        timeline=request.timeline,
        region=request.region,
    )

    return CareerPlanResponse(
        target_role=result.target_role,
        current_fit=result.current_fit,
        skill_gaps=list(result.skill_gaps),
        recommended_courses=[PlannedCourse(**c) for c in result.recommended_courses],
        short_term_actions=list(result.short_term_actions),
        medium_term_actions=list(result.medium_term_actions),
        notes=list(result.notes),
        sources=list(result.sources),
    )
