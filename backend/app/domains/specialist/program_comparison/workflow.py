"""Programme-comparison orchestration behind the public domain interface.

``ComparisonInput`` is the only data source: the catalogue, the applicant
and what was asked all come from the upstream agent. This module never
retrieves anything itself.

The domain's half of the workflow (S1, S2 and S7 live in the tools
layer): S3 each programme's facts by aspect (stages/s3_facts/), S4 each
read against the applicant (stages/s4_fit/), S6 the mode's result
(stages/s6_modes/). This module is the conductor — it implements no rule
itself, only sequences the stages and turns failures into diagnostics:
S3 and S6 are required, S4 is not (without it the facts still answer,
unpersonalised).
"""

from __future__ import annotations

from typing import Callable, TypeVar

from app.core.logging import get_logger
from app.domains.specialist.program_comparison.contracts import ComparisonInput
from app.domains.specialist.program_comparison.errors import (
    ErrorCode,
    ProgramComparisonStageError,
    StageName,
    WorkflowDiagnostic,
    WorkflowStageResult,
)
from app.domains.specialist.program_comparison.models import Applicant, ComparisonResult, Conditions
from app.domains.specialist.program_comparison.policy import dimensions as dimension_policy
from app.domains.specialist.program_comparison.stages.s3_facts import views as facts_stage
from app.domains.specialist.program_comparison.stages.s4_fit import applicant as fit_stage
from app.domains.specialist.program_comparison.stages.s6_modes.base import ModeStrategy
from app.domains.specialist.program_comparison.stages.s6_modes.compare import Compare
from app.domains.specialist.program_comparison.stages.s6_modes.detail import Detail
from app.domains.specialist.program_comparison.stages.s6_modes.explore import Explore

logger = get_logger(__name__)
T = TypeVar("T")

MODES: dict[str, ModeStrategy] = {"compare": Compare(), "detail": Detail(), "explore": Explore()}

_NOT_PERSONALISED_NOTE = (
    "Nothing about your situation (residency, test scores, work experience, plans) is on file, so this "
    "lays out the programmes' published facts without relating them to you."
)
_FIT_FAILED_NOTE = "Your situation couldn't be read against the programmes this time; the published facts still stand."
_INTAKE_NOTE = (
    "The figures are for the {years} intake, not the AY{intake}/{next:02d} intake you plan for; "
    "fees and dates usually change between intakes."
)
_NO_MATCHES_NOTE = "No programme in the comparison data meets those conditions."
_UNSUPPORTED_NOTE = "Rankings and reputation aren't covered by the comparison data, so they aren't compared here."


def _applicant(request: ComparisonInput) -> Applicant:
    a = request.applicant
    return Applicant(
        residency=a.residency, is_nus_alumnus=a.is_nus_alumnus, english_medium_degree=a.english_medium_degree,
        tests=tuple(t.model_dump() for t in a.tests), work_band=a.total_work_years,
        decision_factors=tuple(a.decision_factors), intake_year=a.intake_year,
        target_role=a.target_role, target_skills=tuple(a.target_skills),
    )


def _run_required(request_id: str, stage: StageName, code: str, results: list[WorkflowStageResult],
                  summary: str, action: Callable[[], T]) -> T:
    try:
        value = action()
    except ProgramComparisonStageError:
        raise
    except Exception as exc:
        logger.exception("programme comparison stage failed request_id=%s stage=%s", request_id, stage)
        results.append(WorkflowStageResult(stage, "failed", f"{summary} failed.", diagnostic_codes=(code,)))
        raise ProgramComparisonStageError(
            request_id=request_id, stage=stage, code=code, message=f"Programme comparison failed at {stage}.",
            retryable=False, stage_results=tuple(results),
        ) from exc
    results.append(WorkflowStageResult(stage, "success", summary))
    return value


def compare(request: ComparisonInput) -> ComparisonResult:
    rid = request.request_id
    applicant = _applicant(request)
    conditions = Conditions(tuple(request.conditions.countries), request.conditions.study_mode,
                            tuple(request.conditions.categories))
    dims = dimension_policy.order(request.dimensions, applicant.decision_factors)
    target_id = next(p.program_id for p in request.programs if p.is_target)
    subject_ids = tuple(request.subject_ids)
    wanted = None if request.mode == "explore" else {target_id, *subject_ids}
    programs = [p for p in request.programs if wanted is None or p.program_id in wanted]

    results: list[WorkflowStageResult] = []
    diagnostics: list[WorkflowDiagnostic] = []
    notes: list[str] = []

    views = _run_required(rid, "program_facts", ErrorCode.PROGRAM_FACTS_FAILED, results,
                          f"Laid out {len(programs)} programme(s) by aspect.",
                          lambda: {p.program_id: facts_stage.build(p.model_dump()) for p in programs})

    try:
        fits = {pid: fit_stage.fit(view, applicant, request.today) for pid, view in views.items()}
        results.append(WorkflowStageResult("applicant_fit", "success", "Read the programmes against the applicant."))
    except Exception:
        logger.exception("programme comparison: applicant fit failed request_id=%s", rid)
        fits = {}
        diagnostics.append(WorkflowDiagnostic("applicant_fit", ErrorCode.APPLICANT_FIT_FAILED, _FIT_FAILED_NOTE, True))
        results.append(WorkflowStageResult("applicant_fit", "degraded", "Applicant fit failed; facts only.",
                                           diagnostic_codes=(ErrorCode.APPLICANT_FIT_FAILED,)))
        notes.append(_FIT_FAILED_NOTE)

    baseline, subjects, matches, contrasts = _run_required(
        rid, "result_assembly", ErrorCode.RESULT_ASSEMBLY_FAILED, results, f"Assembled the {request.mode} result.",
        lambda: MODES[request.mode].assemble(views, fits, target_id=target_id, subject_ids=subject_ids,
                                             dimensions=dims, conditions=conditions))

    if not applicant.known:
        diagnostics.append(WorkflowDiagnostic("applicant_fit", ErrorCode.NOT_PERSONALISED, _NOT_PERSONALISED_NOTE, False))
        notes.append(_NOT_PERSONALISED_NOTE)
    mismatched = sorted({views[pid].intake_year for pid, fit in fits.items() if fit.intake_mismatch})
    if mismatched:
        note = _INTAKE_NOTE.format(years=", ".join(map(str, mismatched)), intake=applicant.intake_year,
                                   next=(applicant.intake_year + 1) % 100)
        diagnostics.append(WorkflowDiagnostic("applicant_fit", ErrorCode.INTAKE_MISMATCH, note, False))
        notes.append(note)
    if request.mode == "explore" and not matches:
        diagnostics.append(WorkflowDiagnostic("result_assembly", ErrorCode.NO_MATCHING_PROGRAMMES, _NO_MATCHES_NOTE, False))
        notes.append(_NO_MATCHES_NOTE)
    unsupported = tuple(f for f in applicant.decision_factors if f in dimension_policy.UNSUPPORTED_FACTORS)
    if unsupported:
        notes.append(_UNSUPPORTED_NOTE)

    return ComparisonResult(
        request_id=rid, mode=request.mode, today=request.today, dimensions=dims, baseline=baseline,
        subjects=subjects, matches=matches, contrasts=contrasts, personalised=applicant.known and bool(fits),
        unsupported_factors=unsupported, notes=tuple(notes), diagnostics=tuple(diagnostics),
        stage_results=tuple(results),
    )
