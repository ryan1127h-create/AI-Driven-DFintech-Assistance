"""Career-planning orchestration behind the public domain interface.

``CareerPlanningInput`` is the only data source: the student's evidence
and situation, the role catalogue and the course-to-role links all come
from the upstream agent. This module never retrieves anything itself.

The domain's half of the workflow (S1, S2 and S7 live in the tools
layer): S3 skill evidence (stages/s3_evidence/), S4 role fit
(stages/s4_fit/), S5 roadmap (stages/s5_roadmap/), S6 the mode's result
(stages/s6_modes/). This module is the conductor — it implements no rule
itself, only sequences the stages and turns failures into diagnostics:
S3, S4 and S6 are required (a failure there fails the request), the
roadmap is not (a plan without one is still returned, degraded).
"""

from __future__ import annotations

from typing import Callable, TypeVar

from app.core.logging import get_logger
from app.domains.specialist.career_planning.contracts import CareerPlanningInput
from app.domains.specialist.career_planning.errors import (
    CareerPlanningStageError,
    ErrorCode,
    StageName,
    StageStatus,
    WorkflowDiagnostic,
    WorkflowStageResult,
)
from app.domains.specialist.career_planning.models import (
    CareerPlanningResult,
    CourseLink,
    FunctionExperience,
    ModeInput,
    ReadinessGap,
    RoadmapContext,
    RoleDefinition,
    StudentEvidence,
)
from app.domains.specialist.career_planning.policy import skill_evidence
from app.domains.specialist.career_planning.stages.s3_evidence import skills
from app.domains.specialist.career_planning.stages.s4_fit import roles as role_fit
from app.domains.specialist.career_planning.stages.s5_roadmap import planner
from app.domains.specialist.career_planning.stages.s6_modes.base import ModeStrategy
from app.domains.specialist.career_planning.stages.s6_modes.compare import Compare
from app.domains.specialist.career_planning.stages.s6_modes.exploration import Exploration
from app.domains.specialist.career_planning.stages.s6_modes.plan import Plan

logger = get_logger(__name__)
T = TypeVar("T")

MODES: dict[str, ModeStrategy] = {
    "exploration": Exploration(),
    "plan": Plan(),
    "compare": Compare(),
}

_NO_EVIDENCE_NOTE = (
    "Your profile doesn't yet hold any skill evidence (skill levels, experience, tech stack or courses), "
    "so every skill is unassessed. Adding them makes this advice specific to you."
)
_ROADMAP_FAILED_NOTE = "A dated roadmap couldn't be built this time; the skill assessment still stands."


def _student_evidence(request: CareerPlanningInput) -> StudentEvidence:
    profile = request.profile
    facts = {}
    for key in skill_evidence.EVIDENCE_FIELDS - {"function_experience"}:
        value = getattr(profile, key)
        if isinstance(value, list):
            value = tuple(value)
        if value not in (None, ()):
            facts[key] = value
    return StudentEvidence(
        facts=facts,
        functions=tuple(FunctionExperience(f.key, f.internship) for f in profile.function_experience),
        completed_courses=tuple(profile.completed_courses),
        current_courses=tuple(profile.current_courses),
    )


def _roles(request: CareerPlanningInput) -> dict[str, RoleDefinition]:
    return {
        r.tag: RoleDefinition(r.tag, r.name, r.definition, tuple(r.required_skills))
        for r in request.role_catalog
    }


def _links(request: CareerPlanningInput) -> tuple[CourseLink, ...]:
    return tuple(CourseLink(link.code, link.title, frozenset(link.tags)) for link in request.course_links)


def _roadmap_context(request: CareerPlanningInput) -> RoadmapContext:
    s = request.situation
    return RoadmapContext(
        today=request.today,
        stage=s.stage,
        expected_grad_term=s.expected_grad_term,
        job_search_timeline=s.job_search_timeline,
        internship_status=s.internship_status,
        capstone_intent=s.capstone_intent,
        target_markets=tuple(s.target_markets),
    )


def plan_career(request: CareerPlanningInput) -> CareerPlanningResult:
    """Run the domain workflow from one validated upstream-agent report."""
    rid = request.request_id
    notes: list[str] = []
    diagnostics: list[WorkflowDiagnostic] = []
    stage_results: list[WorkflowStageResult] = []
    mode = MODES[request.mode]
    _record(stage_results, diagnostics, stage="input_validation",
            summary="The upstream-agent report passed schema validation.",
            output={"schema_version": request.schema_version, "mode": request.mode,
                    "target_roles": list(request.target_roles), "role_count": len(request.role_catalog)})

    evidence = _student_evidence(request)
    links = _links(request)
    catalog = _roles(request)

    assessments = _required(rid, "skill_evidence", ErrorCode.SKILL_EVIDENCE_FAILED,
                            "The student's skill evidence could not be graded.", stage_results,
                            lambda: skills.assess_skills(evidence, links))
    has_evidence = skills.has_any_evidence(assessments)
    if not has_evidence:
        notes.append(_NO_EVIDENCE_NOTE)
        _diagnose(diagnostics, rid, "skill_evidence", ErrorCode.NO_PROFILE_EVIDENCE,
                  "No skill evidence was supplied; every skill is unknown.")
    _record(stage_results, diagnostics, stage="skill_evidence", summary="Every role skill was graded.",
            output={"statuses": {s: a.status for s, a in assessments.items()}})

    preferred = frozenset(request.preferred_roles)

    def fit_roles():
        if mode.ranks_all_roles:
            return tuple(role_fit.rank_roles(tuple(catalog.values()), assessments, evidence, links, preferred))
        return tuple(role_fit.fit_role(catalog[t], assessments, evidence, links, preferred)
                     for t in request.target_roles)

    fits = _required(rid, "role_fit", ErrorCode.ROLE_FIT_FAILED,
                     "Role fit could not be computed.", stage_results, fit_roles)
    _record(stage_results, diagnostics, stage="role_fit", summary="Role fit was computed.",
            output={"fits": {f.role.tag: f.fit for f in fits}})

    roadmap = None
    if mode.needs_roadmap:
        target = fits[0]
        try:
            roadmap = planner.build_roadmap(
                _roadmap_context(request),
                tuple(assessments[s] for s in target.role.required_skills),
                tuple(ReadinessGap(g.area, g.level, g.required) for g in request.readiness_gaps),
            )
        except Exception:
            logger.exception("career planning roadmap failed request_id=%s", rid)
            notes.append(_ROADMAP_FAILED_NOTE)
            _diagnose(diagnostics, rid, "roadmap", ErrorCode.ROADMAP_FAILED,
                      "The roadmap could not be built.", retryable=True)
        else:
            if roadmap.graduation_estimated:
                _diagnose(diagnostics, rid, "roadmap", ErrorCode.NO_GRADUATION_TERM,
                          "No graduation term was supplied; it was estimated.")
        _record(stage_results, diagnostics, stage="roadmap", summary="The dated roadmap was built.",
                output={"phases": [p.kind for p in roadmap.phases] if roadmap else []})
    else:
        _record(stage_results, diagnostics, stage="roadmap", status="skipped",
                summary="This mode has no roadmap.", output={})

    output = _required(rid, "result_assembly", ErrorCode.RESULT_ASSEMBLY_FAILED,
                       "The result could not be assembled.", stage_results,
                       lambda: mode.assemble(ModeInput(assessments=assessments, fits=fits, roadmap=roadmap)))
    if any(f.low_confidence for f in output.roles):
        _diagnose(diagnostics, rid, "result_assembly", ErrorCode.LOW_CONFIDENCE_FIT,
                  "At least one role fit rests mostly on unknown skills.")
    notes.extend(output.notes)
    _record(stage_results, diagnostics, stage="result_assembly", summary="The mode's result was assembled.",
            output={"roles": [f.role.tag for f in output.roles]})

    degraded = any(d.code in (ErrorCode.ROADMAP_FAILED,) for d in diagnostics)
    return CareerPlanningResult(
        request_id=rid,
        workflow_status="degraded" if degraded else "complete",
        mode=request.mode,
        roles=output.roles,
        skills=output.skills,
        roadmap=output.roadmap,
        comparison=output.comparison,
        has_profile_evidence=has_evidence,
        notes=tuple(dict.fromkeys(notes)),
        sources=tuple(request.evidence_sources),
        diagnostics=tuple(diagnostics),
        stage_results=tuple(stage_results),
    )


def _required(
    request_id: str,
    stage: StageName,
    code: str,
    message: str,
    stage_results: list[WorkflowStageResult],
    operation: Callable[[], T],
) -> T:
    """Wrap an indispensable stage without exposing its internal exception."""
    try:
        return operation()
    except CareerPlanningStageError:
        raise
    except Exception as exc:
        logger.exception("career planning stage failed request_id=%s stage=%s code=%s", request_id, stage, code)
        raise CareerPlanningStageError(
            request_id=request_id, stage=stage, code=code, message=message, retryable=False,
            stage_results=(*stage_results, WorkflowStageResult(
                stage=stage, status="failed", summary=message, diagnostic_codes=(code,))),
        ) from exc


def _record(
    stage_results: list[WorkflowStageResult],
    diagnostics: list[WorkflowDiagnostic],
    *,
    stage: StageName,
    summary: str,
    output: dict[str, object],
    status: StageStatus | None = None,
) -> None:
    """Append one stage result, degraded when the stage raised diagnostics."""
    codes = tuple(d.code for d in diagnostics if d.stage == stage)
    stage_results.append(WorkflowStageResult(
        stage=stage, status=status or ("degraded" if codes else "success"),
        summary=summary, output=output, diagnostic_codes=codes,
    ))


def _diagnose(
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
    stage: StageName,
    code: str,
    message: str,
    retryable: bool = False,
) -> None:
    diagnostics.append(WorkflowDiagnostic(stage=stage, code=code, message=message, retryable=retryable))
    logger.info("career planning degraded request_id=%s stage=%s code=%s", request_id, stage, code)
