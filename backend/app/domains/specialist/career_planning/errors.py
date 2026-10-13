"""Structured diagnostics for the career-planning workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.errors import ServiceUnavailableError

StageName = Literal[
    "input_validation",
    "skill_evidence",
    "role_fit",
    "roadmap",
    "result_assembly",
    "response_serialization",
]
StageStatus = Literal["success", "degraded", "skipped", "failed"]


class ErrorCode:
    """Stable codes used by callers, tests, and logs."""

    INPUT_INVALID = "CP_INPUT_INVALID"
    SKILL_EVIDENCE_FAILED = "CP_SKILL_EVIDENCE_FAILED"
    ROLE_FIT_FAILED = "CP_ROLE_FIT_FAILED"
    ROADMAP_FAILED = "CP_ROADMAP_FAILED"
    RESULT_ASSEMBLY_FAILED = "CP_RESULT_ASSEMBLY_FAILED"
    RESPONSE_SERIALIZATION_FAILED = "CP_RESPONSE_SERIALIZATION_FAILED"
    # Degradations returned alongside a result.
    NO_PROFILE_EVIDENCE = "CP_NO_PROFILE_EVIDENCE"
    LOW_CONFIDENCE_FIT = "CP_LOW_CONFIDENCE_FIT"
    NO_GRADUATION_TERM = "CP_NO_GRADUATION_TERM"


@dataclass(frozen=True)
class WorkflowDiagnostic:
    """A recoverable problem returned with a degraded result."""

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


class CareerPlanningStageError(ServiceUnavailableError):
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
        self.status_code = status_code if status_code is not None else (503 if retryable else 500)

    def response_content(self) -> dict[str, object]:
        """Safe envelope; the original exception stays in server logs."""
        return {
            "detail": str(self),
            "workflow_status": "failed",
            "stage_results": [
                item.response_content(sequence)
                for sequence, item in enumerate(self.stage_results, start=1)
            ],
            "error": {
                "domain": "career_planning",
                "request_id": self.request_id,
                "stage": self.stage,
                "code": self.code,
                "message": str(self),
                "retryable": self.retryable,
            },
        }


def input_validation_error(*, request_id: object, errors: list[dict[str, object]]) -> CareerPlanningStageError:
    """The same safe validation failure for every caller."""
    safe_errors = [
        {
            "location": ".".join(map(str, item.get("loc", ()))),
            "message": str(item.get("msg", "Invalid value.")),
            "type": str(item.get("type", "validation_error")),
        }
        for item in errors
    ]
    return CareerPlanningStageError(
        request_id=str(request_id),
        stage="input_validation",
        code=ErrorCode.INPUT_INVALID,
        message="The career planning input report is invalid.",
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
