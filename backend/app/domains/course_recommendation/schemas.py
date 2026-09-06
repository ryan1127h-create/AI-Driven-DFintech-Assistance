"""Request/response schemas for the course_recommendation API — kept
separate from the internal domain models (models.py)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.core.logging import get_logger
from app.domains.course_recommendation.errors import (
    CourseRecommendationStageError,
    ErrorCode,
    StageName,
    StageStatus,
    WorkflowStageResult,
)
from app.domains.course_recommendation.models import Priority, RecommendationResult

logger = get_logger(__name__)


class RecommendedCourse(BaseModel):
    course_code: str
    course_title: str
    units: int
    section: str
    offered_terms: list[str]
    course_time: str | None
    priority: Priority
    matched_skills: list[str]
    reason: str


class WorkflowDiagnosticResponse(BaseModel):
    stage: StageName
    code: str
    message: str
    retryable: bool


class WorkflowStageResultResponse(BaseModel):
    sequence: int
    stage: StageName
    status: StageStatus
    summary: str
    output: dict[str, object]
    diagnostic_codes: list[str]


class CourseRecommendationErrorResponse(BaseModel):
    domain: Literal["course_recommendation"]
    request_id: str
    stage: StageName
    code: str
    message: str
    retryable: bool


class CourseRecommendationFailureResponse(BaseModel):
    detail: str
    workflow_status: Literal["failed"]
    stage_results: list[WorkflowStageResultResponse]
    error: CourseRecommendationErrorResponse


class CourseRecommendationResponse(BaseModel):
    request_id: str
    workflow_status: Literal["ok", "degraded"]
    target_role: str | None
    recommended_courses: list[RecommendedCourse]
    skill_gaps: list[str]
    completed_recognized: list[str]
    completed_unrecognized: list[str]
    completed_units: int
    notes: list[str]
    sources: list[str]
    diagnostics: list[WorkflowDiagnosticResponse]
    stage_results: list[WorkflowStageResultResponse]


def _stage_responses(
    stages: tuple[WorkflowStageResult, ...],
) -> list[WorkflowStageResultResponse]:
    return [
        WorkflowStageResultResponse.model_validate(
            item.response_content(sequence),
        )
        for sequence, item in enumerate(stages, start=1)
    ]


def response_from_result(result: RecommendationResult) -> CourseRecommendationResponse:
    """Map the domain result to the one shared HTTP/internal response shape."""
    try:
        stages = (
            *result.stage_results,
            WorkflowStageResult(
                stage="response_serialization",
                status="success",
                summary="The public response was serialized successfully.",
                output={"response_ready": True},
            ),
        )
        return CourseRecommendationResponse(
            request_id=result.request_id,
            workflow_status=result.workflow_status,
            target_role=result.target_role,
            recommended_courses=[
                RecommendedCourse.model_validate(item)
                for item in result.recommendations
            ],
            skill_gaps=list(result.skill_gaps),
            completed_recognized=list(result.completed_recognized),
            completed_unrecognized=list(result.completed_unrecognized),
            completed_units=result.completed_units,
            notes=list(result.notes),
            sources=list(result.sources),
            diagnostics=[
                WorkflowDiagnosticResponse(
                    stage=item.stage,
                    code=item.code,
                    message=item.message,
                    retryable=item.retryable,
                )
                for item in result.diagnostics
            ],
            stage_results=_stage_responses(stages),
        )
    except Exception as exc:
        logger.exception(
            "course recommendation response serialization failed "
            "request_id=%s code=%s",
            result.request_id,
            ErrorCode.RESPONSE_SERIALIZATION_FAILED,
        )
        raise CourseRecommendationStageError(
            request_id=result.request_id,
            stage="response_serialization",
            code=ErrorCode.RESPONSE_SERIALIZATION_FAILED,
            message="The course recommendation response could not be serialized.",
            retryable=False,
            stage_results=(
                *result.stage_results,
                WorkflowStageResult(
                    stage="response_serialization",
                    status="failed",
                    summary=("The public response could not be serialized."),
                    diagnostic_codes=(ErrorCode.RESPONSE_SERIALIZATION_FAILED,),
                ),
            ),
        ) from exc
