from fastapi import APIRouter, HTTPException

from app.modules.career_planning import service
from app.modules.career_planning.schemas import (
    CareerPlanRequest,
    CareerPlanResponse,
    PlannedCourse,
)

router = APIRouter()


# Sync `def` on purpose: the service does blocking DB + LLM calls, and
# FastAPI runs sync path operations in a threadpool.
@router.post("/career-plans", response_model=CareerPlanResponse)
def create_career_plan(request: CareerPlanRequest) -> CareerPlanResponse:
    """
    Personal career plan for the current (placeholder) user. Skill gaps and
    course picks come from the course_recommendation module; the LLM only
    writes the narrative, with a deterministic fallback (stated in `notes`).
    """
    try:
        result = service.create_career_plan(
            target_role=request.target_role,
            timeline=request.timeline,
            region=request.region,
        )
    except Exception as exc:
        print(f"[career_planning.api] Error: career plan failed — {exc!r}")
        raise HTTPException(
            status_code=500, detail="Failed to generate the career plan."
        ) from exc

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
