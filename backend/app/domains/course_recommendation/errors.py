"""Structured diagnostics for the course-recommendation workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.errors import ServiceUnavailableError

StageName = Literal[
    "input_validation",
    "role_resolution",
    "course_catalog_materialization",
    "candidate_pool_building",
    "candidate_scope_applying",
    "curriculum_rules_materialization",
    "llm_selection",
    "llm_output_validation",
    "fallback_ranking",
    "result_assembly",
    "source_assembly",
    "response_serialization",
]
StageStatus = Literal["success", "degraded", "skipped", "failed"]


class ErrorCode:
    """Stable codes used by API callers, upstream agents, tests, and logs."""

    INPUT_INVALID = "CR_INPUT_INVALID"
    TARGET_ROLE_MISSING = "CR_TARGET_ROLE_MISSING"
    ROLE_RESOLUTION_FAILED = "CR_ROLE_RESOLUTION_FAILED"
    COURSE_CATALOG_INVALID = "CR_COURSE_CATALOG_INVALID"
    CANDIDATE_POOL_FAILED = "CR_CANDIDATE_POOL_FAILED"
    CANDIDATE_SCOPE_FAILED = "CR_CANDIDATE_SCOPE_FAILED"
    CANDIDATE_CODE_UNKNOWN = "CR_CANDIDATE_CODE_UNKNOWN"
    COMPLETED_COURSE_UNRECOGNIZED = "CR_COMPLETED_COURSE_UNRECOGNIZED"
    NO_ELIGIBLE_COURSES = "CR_NO_ELIGIBLE_COURSES"
    CURRICULUM_RULES_INVALID = "CR_CURRICULUM_RULES_INVALID"
    LLM_SELECTION_FAILED = "CR_LLM_SELECTION_FAILED"
    LLM_RESPONSE_INVALID = "CR_LLM_RESPONSE_INVALID"
    LLM_SELECTION_INSUFFICIENT = "CR_LLM_SELECTION_INSUFFICIENT"
    FALLBACK_RANKING_FAILED = "CR_FALLBACK_RANKING_FAILED"
    NO_MATCHING_COURSES = "CR_NO_MATCHING_COURSES"
    RESULT_ASSEMBLY_FAILED = "CR_RESULT_ASSEMBLY_FAILED"
    SOURCE_ASSEMBLY_FAILED = "CR_SOURCE_ASSEMBLY_FAILED"
    RESPONSE_SERIALIZATION_FAILED = "CR_RESPONSE_SERIALIZATION_FAILED"
    TARGET_TERM_UNSUPPORTED = "CR_TARGET_TERM_UNSUPPORTED"
    WORKLOAD_FILTER_UNSUPPORTED = "CR_WORKLOAD_FILTER_UNSUPPORTED"


@dataclass(frozen=True)
class WorkflowDiagnostic:
    """A recoverable problem returned with a degraded recommendation."""

    stage: StageName
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True)
class WorkflowStageResult:
    """Safe, structured output from one observable workflow stage."""

    stage: StageName
    status: StageStatus
    summary: str
    output: dict[str, object] = field(default_factory=dict)
    diagnostic_codes: tuple[str, ...] = field(default_factory=tuple)

    def response_content(self, sequence: int) -> dict[str, object]:
        return {
            "sequence": sequence,
            "stage": self.stage,
            "status": self.status,
            "summary": self.summary,
            "output": self.output,
            "diagnostic_codes": list(self.diagnostic_codes),
        }


class CourseRecommendationStageError(ServiceUnavailableError):
    """A non-recoverable workflow failure with a precise stage and code."""

    def __init__(
        self,
        *,
        request_id: str,
        stage: StageName,
        code: str,
        message: str,
        retryable: bool,
        status_code: int | None = None,
        stage_results: tuple[WorkflowStageResult, ...] = (),
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.stage = stage
        self.code = code
        self.retryable = retryable
        self.stage_results = stage_results
        self.status_code = (
            status_code if status_code is not None else (503 if retryable else 500)
        )

    def response_content(self) -> dict[str, object]:
        """Safe API envelope; the original exception stays in server logs."""
        return {
            "detail": str(self),
            "workflow_status": "failed",
            "stage_results": [
                item.response_content(sequence)
                for sequence, item in enumerate(self.stage_results, start=1)
            ],
            "error": {
                "domain": "course_recommendation",
                "request_id": self.request_id,
                "stage": self.stage,
                "code": self.code,
                "message": str(self),
                "retryable": self.retryable,
            },
        }


def input_validation_error(
    *,
    request_id: object,
    errors: list[dict[str, object]],
) -> CourseRecommendationStageError:
    """Build the same safe validation failure for HTTP and internal callers."""
    safe_errors: list[dict[str, str]] = []
    for item in errors:
        raw_location = item.get("loc", ())
        location_parts = (
            list(raw_location)
            if isinstance(raw_location, (list, tuple))
            else [raw_location]
        )
        if location_parts and location_parts[0] == "body":
            location_parts = location_parts[1:]
        safe_errors.append(
            {
                "location": ".".join(map(str, location_parts)),
                "message": str(item.get("msg", "Invalid value.")),
                "type": str(item.get("type", "validation_error")),
            }
        )

    return CourseRecommendationStageError(
        request_id=str(request_id),
        stage="input_validation",
        code=ErrorCode.INPUT_INVALID,
        message="The course recommendation input report is invalid.",
        retryable=False,
        status_code=422,
        stage_results=(
            WorkflowStageResult(
                stage="input_validation",
                status="failed",
                summary="The upstream-agent report failed schema validation.",
                output={"errors": safe_errors},
                diagnostic_codes=(ErrorCode.INPUT_INVALID,),
            ),
        ),
    )
