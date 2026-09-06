from fastapi import APIRouter, Depends

from app.domains.auth.interface import get_current_user_id
from app.domains.career_planning import service
from app.domains.career_planning.schemas import (
    CareerPhase,
    CareerPlanRequest,
    CareerPlanResponse,
    SkillAssessment,
)


router = APIRouter()


@router.post("/career-plans", response_model=CareerPlanResponse)
def create_career_plan(
    request: CareerPlanRequest,
    user_id: str = Depends(get_current_user_id),
) -> CareerPlanResponse:
    """Build an evidence-based, phased career-readiness plan."""
    result = service.create_career_plan(
        user_id=user_id,
        target_role=request.target_role,
        timeline=request.timeline,
        region=request.region,
    )

    return CareerPlanResponse(
        target_role=result.target_role,
        current_fit=result.current_fit,
        skill_assessment=[SkillAssessment(**item) for item in result.skill_assessment],
        phases=[CareerPhase(**phase) for phase in result.phases],
        success_indicators=list(result.success_indicators),
        notes=list(result.notes),
        sources=list(result.sources),
    )
