"""The career-planning response schema — the one shape callers receive,
kept separate from the internal domain models (models.py)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from pydantic import BaseModel

from app.domains.specialist.career_planning.errors import (
    CareerPlanningStageError,
    ErrorCode,
    StageName,
    StageStatus,
    WorkflowStageResult,
)
from app.domains.specialist.career_planning.models import (
    ActionKind,
    CareerPlanningResult,
    MilestoneKind,
    Mode,
    PhaseKind,
    SkillStatus,
    WorkflowStatus,
)


class EvidenceItemResponse(BaseModel):
    source: str
    values: list[str]
    points: float
    in_progress: bool
    internship: bool


class SkillAssessmentResponse(BaseModel):
    skill: str
    status: SkillStatus
    points: float
    evidence: list[EvidenceItemResponse]


class RoleResponse(BaseModel):
    tag: str
    name: str
    definition: str
    required_skills: list[str]


class CourseSupportResponse(BaseModel):
    course_codes: list[str]
    taken: list[str]
    taking: list[str]


class RoleFitResponse(BaseModel):
    role: RoleResponse
    fit: float
    unknown_share: float
    low_confidence: bool
    met_skills: list[str]
    partial_skills: list[str]
    missing_skills: list[str]
    unknown_skills: list[str]
    experience: list[str]
    preferred: bool
    support: CourseSupportResponse


class ActionResponse(BaseModel):
    kind: ActionKind
    text: str
    subjects: list[str]


class MilestoneResponse(BaseModel):
    kind: MilestoneKind
    on: date
    label: str
    projected: bool


class PhaseResponse(BaseModel):
    kind: PhaseKind
    name: str
    start: date
    end: date
    actions: list[ActionResponse]
    milestones: list[MilestoneResponse]


class RoadmapResponse(BaseModel):
    phases: list[PhaseResponse]
    graduation_term: str | None
    graduation_estimated: bool
    capstone_cycle_year: int | None
    notes: list[str]


class ComparisonResponse(BaseModel):
    shared_skills: list[str]
    distinct_skills: dict[str, list[str]]


class WorkflowDiagnosticResponse(BaseModel):
    stage: StageName
    code: str
    message: str
    retryable: bool


class StageResultResponse(BaseModel):
    sequence: int
    stage: StageName
    status: StageStatus
    summary: str
    output: dict[str, object]
    diagnostic_codes: list[str]


class CareerPlanningResponse(BaseModel):
    request_id: str
    workflow_status: WorkflowStatus
    mode: Mode
    roles: list[RoleFitResponse]
    skills: list[SkillAssessmentResponse]
    roadmap: RoadmapResponse | None
    comparison: ComparisonResponse | None
    has_profile_evidence: bool
    notes: list[str]
    sources: list[str]
    diagnostics: list[WorkflowDiagnosticResponse]
    stage_results: list[StageResultResponse]


def response_from_result(result: CareerPlanningResult) -> CareerPlanningResponse:
    """Map the domain result to the response shape."""
    try:
        stages = (
            *result.stage_results,
            WorkflowStageResult(stage="response_serialization", status="success",
                                summary="The response was serialized.", output={"response_ready": True}),
        )
        return CareerPlanningResponse(
            request_id=result.request_id,
            workflow_status=result.workflow_status,
            mode=result.mode,
            roles=[asdict(f) for f in result.roles],
            skills=[asdict(s) for s in result.skills],
            roadmap=asdict(result.roadmap) if result.roadmap else None,
            comparison=asdict(result.comparison) if result.comparison else None,
            has_profile_evidence=result.has_profile_evidence,
            notes=list(result.notes),
            sources=list(result.sources),
            diagnostics=[asdict(d) for d in result.diagnostics],
            stage_results=[s.response_content(i) for i, s in enumerate(stages, start=1)],
        )
    except Exception as exc:
        raise CareerPlanningStageError(
            request_id=result.request_id,
            stage="response_serialization",
            code=ErrorCode.RESPONSE_SERIALIZATION_FAILED,
            message="The career planning result could not be serialized.",
            retryable=False,
            stage_results=tuple(result.stage_results),
        ) from exc
