"""Course-recommendation orchestration behind the public domain interface.

``CourseRecommendationInput`` is the only data source. User facts, resolved
role skills, the complete course catalogue, curriculum rules, and provenance
must all be supplied by the upstream agent. This module must never retrieve
missing data from a profile store, repository, or knowledge database.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, TypeVar

from app.core.logging import get_logger
from app.domains.course_recommendation import recommendation_agent, rule_engine
from app.domains.course_recommendation.contracts import CourseRecommendationInput
from app.domains.course_recommendation.errors import (
    CourseRecommendationStageError,
    ErrorCode,
    StageName,
    StageStatus,
    WorkflowDiagnostic,
    WorkflowStageResult,
)
from app.domains.course_recommendation.models import (
    CandidatePool,
    Course,
    CurriculumRule,
    Recommendation,
    RecommendationResult,
    SelectionPick,
)

logger = get_logger(__name__)
T = TypeVar("T")


def recommend_courses(
    request: CourseRecommendationInput,
) -> RecommendationResult:
    """Run the domain workflow from one validated upstream-agent report."""
    notes: list[str] = []
    diagnostics: list[WorkflowDiagnostic] = []
    stage_results: list[WorkflowStageResult] = []
    _record_stage(
        stage_results,
        diagnostics,
        stage="input_validation",
        summary="The upstream-agent report passed schema validation.",
        output={
            "schema_version": request.schema_version,
            "course_count": len(request.course_catalog),
            "curriculum_rule_count": len(request.curriculum_rules),
            "completed_course_count": len(request.background.completed_courses),
            "max_recommendations": request.constraints.max_recommendations,
        },
    )
    role_title, role_skills, courses, rules = _materialize_report(
        request,
        notes,
        diagnostics,
        stage_results,
    )
    pool = _build_scoped_pool(
        request,
        courses,
        role_skills,
        notes,
        diagnostics,
        stage_results,
    )
    picks = _select_picks(
        request,
        pool,
        rules,
        role_title,
        role_skills,
        notes,
        diagnostics,
        stage_results,
    )
    return _assemble_result(
        request,
        role_title,
        role_skills,
        courses,
        pool,
        picks,
        notes,
        diagnostics,
        stage_results,
    )


def _materialize_report(
    request: CourseRecommendationInput,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> tuple[str | None, list[str], list[Course], list[CurriculumRule]]:
    """Convert the validated report into internal role, course, and rule models."""
    role_title, role_skills = _run_required_stage(
        request_id=request.request_id,
        stage="role_resolution",
        code=ErrorCode.ROLE_RESOLUTION_FAILED,
        message="The role profile supplied in the report could not be resolved.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _resolve_role_profile(
            request,
            notes,
            diagnostics,
            request.request_id,
        ),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="role_resolution",
        summary="Role evidence from the report was resolved.",
        output={
            "role_profile_supplied": request.role_profile is not None,
            "target_role": role_title,
            "required_skills": role_skills,
        },
    )
    courses = _run_required_stage(
        request_id=request.request_id,
        stage="course_catalog_materialization",
        code=ErrorCode.COURSE_CATALOG_INVALID,
        message=(
            "The course catalogue supplied in the report could not be " "materialized."
        ),
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _courses_from_report(request),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="course_catalog_materialization",
        summary="The supplied course catalogue was materialized.",
        output={
            "course_count": len(courses),
            "course_codes": [course.code for course in courses],
            "recommendable_course_codes": [
                course.code for course in courses if course.can_recommend
            ],
            "display_data": [
                {
                    "course_code": course.code,
                    "offered_terms": list(course.offered_terms),
                    "course_time": course.course_time,
                }
                for course in courses
            ],
        },
    )
    rules = _run_required_stage(
        request_id=request.request_id,
        stage="curriculum_rules_materialization",
        code=ErrorCode.CURRICULUM_RULES_INVALID,
        message=(
            "The curriculum rules supplied in the report could not be " "materialized."
        ),
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _rules_from_report(request),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="curriculum_rules_materialization",
        summary="The supplied curriculum rules were materialized.",
        output={
            "rule_count": len(rules),
            "rules": [
                {
                    "rule_key": rule.rule_key,
                    "category": rule.category,
                    "intake": rule.intake,
                }
                for rule in rules
            ],
        },
    )
    return role_title, role_skills, courses, rules


def _build_scoped_pool(
    request: CourseRecommendationInput,
    courses: list[Course],
    role_skills: list[str],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> CandidatePool:
    """Apply hard eligibility and caller-supplied candidate-scope rules."""
    pool = _run_required_stage(
        request_id=request.request_id,
        stage="candidate_pool_building",
        code=ErrorCode.CANDIDATE_POOL_FAILED,
        message="The eligible course pool could not be built.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: rule_engine.build_candidate_pool(
            courses,
            request.background.completed_courses,
            role_skills,
        ),
    )
    _record_pool_diagnostics(pool, notes, diagnostics, request.request_id)
    _record_stage(
        stage_results,
        diagnostics,
        stage="candidate_pool_building",
        summary="Hard eligibility rules produced the candidate pool.",
        output={
            "eligible_course_codes": [course.code for course in pool.eligible],
            "excluded_courses": list(pool.excluded_courses),
            "skill_gaps": list(pool.skill_gaps),
            "completed_recognized": list(pool.completed_recognized),
            "completed_unrecognized": list(pool.completed_unrecognized),
            "completed_units": pool.completed_units,
        },
    )

    pool = _run_required_stage(
        request_id=request.request_id,
        stage="candidate_scope_applying",
        code=ErrorCode.CANDIDATE_SCOPE_FAILED,
        message="The requested course scope could not be applied.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _apply_candidate_scope(
            pool,
            request.constraints.candidate_course_codes,
            courses,
            notes,
            diagnostics,
            request.request_id,
        ),
    )
    _note_unsupported_filters(request, notes, diagnostics, request.request_id)

    if not pool.eligible:
        _add_diagnostic(
            diagnostics,
            request_id=request.request_id,
            stage="candidate_scope_applying",
            code=ErrorCode.NO_ELIGIBLE_COURSES,
            message=(
                "No eligible courses remained after applying completion, "
                "preclusion, and scope rules."
            ),
            retryable=False,
        )
    _record_stage(
        stage_results,
        diagnostics,
        stage="candidate_scope_applying",
        summary="The caller-supplied candidate scope was applied.",
        output={
            "requested_course_codes": request.constraints.candidate_course_codes,
            "scoped_eligible_course_codes": [course.code for course in pool.eligible],
            "eligible_count": len(pool.eligible),
        },
    )
    return pool


def _record_pool_diagnostics(
    pool: CandidatePool,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
) -> None:
    notes.extend(pool.notes)
    if not pool.completed_unrecognized:
        return
    _add_diagnostic(
        diagnostics,
        request_id=request_id,
        stage="candidate_pool_building",
        code=ErrorCode.COMPLETED_COURSE_UNRECOGNIZED,
        message="Some completed courses were not found in the catalogue: "
        + ", ".join(pool.completed_unrecognized),
        retryable=False,
    )


def _select_picks(
    request: CourseRecommendationInput,
    pool: CandidatePool,
    rules: list[CurriculumRule],
    role_title: str | None,
    role_skills: list[str],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> list[SelectionPick]:
    """Use the model selector and fall back to deterministic ranking if needed."""
    if not pool.eligible:
        for stage, summary in (
            ("llm_selection", "LLM selection was skipped because the pool was empty."),
            (
                "llm_output_validation",
                "LLM output validation was skipped because no model call ran.",
            ),
            (
                "fallback_ranking",
                "Fallback ranking was skipped because the pool was empty.",
            ),
        ):
            _record_stage(
                stage_results,
                diagnostics,
                stage=stage,
                status="skipped",
                summary=summary,
                output={"reason": "no_eligible_courses"},
            )
        return []

    preferences = _preference_keywords(request)
    selection = _run_required_stage(
        request_id=request.request_id,
        stage="llm_selection",
        code=ErrorCode.LLM_SELECTION_FAILED,
        message="The course-selection stage failed unexpectedly.",
        retryable=True,
        stage_results=stage_results,
        operation=lambda: recommendation_agent.select_courses(
            pool,
            rules,
            role_title,
            preferences,
            student_context=_student_context(request),
            max_picks=request.constraints.max_recommendations,
            request_id=request.request_id,
        ),
    )
    if selection.picks is not None:
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_selection",
            summary="The LLM selector returned a response.",
            output={
                "model_invoked": True,
                "response_received": True,
                "eligible_course_count": len(pool.eligible),
                "selection_limit": request.constraints.max_recommendations,
            },
        )
        notes.extend(selection.notes)
        picks = list(selection.picks)
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_output_validation",
            summary="The model selections passed code-side validation.",
            output={
                "validated_picks": picks,
                "model_notes": list(selection.notes),
            },
        )
        _record_stage(
            stage_results,
            diagnostics,
            stage="fallback_ranking",
            status="skipped",
            summary="Fallback ranking was not needed.",
            output={"reason": "llm_selection_valid"},
        )
    else:
        picks = _fallback_after_selection_failure(
            request,
            pool,
            role_skills,
            preferences,
            selection,
            notes,
            diagnostics,
            stage_results,
        )

    # Keep a service-level cap even though both selectors receive the limit.
    # This protects the public result if a selector implementation regresses.
    return picks[: request.constraints.max_recommendations]


def _fallback_after_selection_failure(
    request: CourseRecommendationInput,
    pool: CandidatePool,
    role_skills: list[str],
    preferences: list[str],
    selection: recommendation_agent.SelectionOutcome,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> list[SelectionPick]:
    error_code = selection.error_code or ErrorCode.LLM_SELECTION_FAILED
    validation_failed = error_code in {
        ErrorCode.LLM_RESPONSE_INVALID,
        ErrorCode.LLM_SELECTION_INSUFFICIENT,
    }
    diagnostic_stage: StageName = (
        "llm_output_validation" if validation_failed else "llm_selection"
    )
    _add_diagnostic(
        diagnostics,
        request_id=request.request_id,
        stage=diagnostic_stage,
        code=error_code,
        message=selection.error_message
        or "The model selector could not produce a usable result.",
        retryable=selection.retryable,
    )
    if validation_failed:
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_selection",
            summary="The LLM selector returned a response.",
            output={"model_invoked": True, "response_received": True},
        )
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_output_validation",
            status="degraded",
            summary="The model response failed code-side validation.",
            output={"validated_picks": []},
            diagnostic_codes=(error_code,),
        )
    else:
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_selection",
            status="degraded",
            summary="The LLM selector was unavailable.",
            output={"model_invoked": True, "response_received": False},
            diagnostic_codes=(error_code,),
        )
        _record_stage(
            stage_results,
            diagnostics,
            stage="llm_output_validation",
            status="skipped",
            summary="LLM output validation was skipped because no response arrived.",
            output={"reason": "llm_response_unavailable"},
        )
    picks = _run_required_stage(
        request_id=request.request_id,
        stage="fallback_ranking",
        code=ErrorCode.FALLBACK_RANKING_FAILED,
        message="The deterministic fallback ranking failed.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _fallback_picks(
            pool,
            role_skills,
            preferences,
            request.constraints.max_recommendations,
        ),
    )
    notes.append(
        "Courses were selected by deterministic rules: the language "
        "model selector was unavailable for this request."
    )
    if not picks:
        _add_diagnostic(
            diagnostics,
            stage="fallback_ranking",
            request_id=request.request_id,
            code=ErrorCode.NO_MATCHING_COURSES,
            message=(
                "The deterministic fallback found no courses matching "
                "the available signals."
            ),
            retryable=False,
        )
    _record_stage(
        stage_results,
        diagnostics,
        stage="fallback_ranking",
        summary="Deterministic fallback ranking produced the selections.",
        output={
            "selected_course_codes": [pick["course_code"] for pick in picks],
            "selection_count": len(picks),
        },
    )
    return picks


def _assemble_result(
    request: CourseRecommendationInput,
    role_title: str | None,
    role_skills: list[str],
    courses: list[Course],
    pool: CandidatePool,
    picks: list[SelectionPick],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> RecommendationResult:
    """Attach catalogue facts, sources, and workflow diagnostics."""
    recommendations = _run_required_stage(
        request_id=request.request_id,
        stage="result_assembly",
        code=ErrorCode.RESULT_ASSEMBLY_FAILED,
        message="The recommendation result could not be assembled.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _assemble_recommendations(picks, pool, role_skills),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="result_assembly",
        summary="Catalogue facts were attached to the validated selections.",
        output={
            "recommended_course_codes": [
                item["course_code"] for item in recommendations
            ],
            "recommendation_count": len(recommendations),
        },
    )
    sources = _run_required_stage(
        request_id=request.request_id,
        stage="source_assembly",
        code=ErrorCode.SOURCE_ASSEMBLY_FAILED,
        message="The recommendation sources could not be assembled.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _sources_for(
            recommendations,
            courses,
            request.evidence_sources,
        ),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="source_assembly",
        summary="Evidence sources were assembled and deduplicated.",
        output={"source_count": len(sources), "sources": list(sources)},
    )

    return RecommendationResult(
        target_role=role_title,
        recommendations=recommendations,
        skill_gaps=pool.skill_gaps,
        completed_recognized=pool.completed_recognized,
        completed_unrecognized=pool.completed_unrecognized,
        completed_units=pool.completed_units,
        notes=tuple(notes),
        sources=sources,
        workflow_status="degraded" if diagnostics else "ok",
        diagnostics=tuple(diagnostics),
        stage_results=tuple(stage_results),
        request_id=request.request_id,
    )


def _run_required_stage(
    *,
    request_id: str,
    stage: StageName,
    code: str,
    message: str,
    retryable: bool,
    stage_results: list[WorkflowStageResult],
    operation: Callable[[], T],
) -> T:
    """Wrap an indispensable stage without exposing its internal exception."""
    try:
        return operation()
    except CourseRecommendationStageError:
        raise
    except Exception as exc:
        logger.exception(
            "course recommendation stage failed request_id=%s stage=%s code=%s",
            request_id,
            stage,
            code,
        )
        raise CourseRecommendationStageError(
            request_id=request_id,
            stage=stage,
            code=code,
            message=message,
            retryable=retryable,
            stage_results=(
                *stage_results,
                WorkflowStageResult(
                    stage=stage,
                    status="failed",
                    summary=message,
                    diagnostic_codes=(code,),
                ),
            ),
        ) from exc


def _record_stage(
    stage_results: list[WorkflowStageResult],
    diagnostics: list[WorkflowDiagnostic],
    *,
    stage: StageName,
    summary: str,
    output: dict[str, object],
    status: StageStatus | None = None,
    diagnostic_codes: tuple[str, ...] | None = None,
) -> None:
    """Append one safe stage result, deriving degradation from diagnostics."""
    stage_diagnostics = tuple(item.code for item in diagnostics if item.stage == stage)
    stage_results.append(
        WorkflowStageResult(
            stage=stage,
            status=status or ("degraded" if stage_diagnostics else "success"),
            summary=summary,
            output=output,
            diagnostic_codes=(
                stage_diagnostics if diagnostic_codes is None else diagnostic_codes
            ),
        )
    )


def _add_diagnostic(
    diagnostics: list[WorkflowDiagnostic],
    *,
    request_id: str,
    stage: StageName,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    diagnostics.append(
        WorkflowDiagnostic(
            stage=stage,
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    logger.warning(
        "course recommendation degraded request_id=%s stage=%s code=%s",
        request_id,
        stage,
        code,
    )


def _preference_keywords(request: CourseRecommendationInput) -> list[str]:
    """Preference text that both the LLM and deterministic fallback can use."""
    values = [
        *request.preferences.course_styles,
        *request.preferences.other_preferences,
    ]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _student_context(request: CourseRecommendationInput) -> list[str]:
    """Structured background facts the selector may cite when personalising."""
    fields = (
        ("target industry", request.goals.target_industry),
        ("academic background", request.background.academic_background),
        ("technical level", request.background.tech_level),
        ("school tier", request.background.school_tier),
    )
    context = [f"{label}: {value}" for label, value in fields if value is not None]
    if request.background.work_years is not None:
        context.append(f"work experience: {request.background.work_years} years")
    return context


def _apply_candidate_scope(
    pool: CandidatePool,
    requested_codes: list[str] | None,
    courses: list[Course],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
) -> CandidatePool:
    """Restrict the eligible pool when the upstream report supplies a scope."""
    if requested_codes is None:
        return pool

    catalogue_codes = {course.code for course in courses}
    unknown = [code for code in requested_codes if code not in catalogue_codes]
    if unknown:
        message = (
            "Candidate course codes not found in the catalogue and ignored: "
            + ", ".join(unknown)
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request_id,
            stage="candidate_scope_applying",
            code=ErrorCode.CANDIDATE_CODE_UNKNOWN,
            message=message,
            retryable=False,
        )

    allowed = set(requested_codes)
    return replace(
        pool,
        eligible=tuple(course for course in pool.eligible if course.code in allowed),
    )


def _note_unsupported_filters(
    request: CourseRecommendationInput,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
) -> None:
    """Make unsupported constraints visible instead of pretending they ran."""
    if request.constraints.target_term is not None:
        message = (
            "A target term was supplied, but offered-term data is optional display "
            "metadata and may be incomplete, so it was not used as a hard filter."
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request_id,
            stage="candidate_scope_applying",
            code=ErrorCode.TARGET_TERM_UNSUPPORTED,
            message=message,
            retryable=False,
        )
    if request.preferences.acceptable_workload is not None:
        message = (
            "A workload preference was supplied, but module credits are not a "
            "comparable workload measure, so it was not used as a hard filter."
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request_id,
            stage="candidate_scope_applying",
            code=ErrorCode.WORKLOAD_FILTER_UNSUPPORTED,
            message=message,
            retryable=False,
        )


def _resolve_role_profile(
    request: CourseRecommendationInput,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
) -> tuple[str | None, list[str]]:
    """Use only the role evidence already resolved in the input report."""
    if request.role_profile is None:
        message = (
            "No target role profile was supplied by the upstream agent; "
            "recommendations are not role-matched."
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request_id,
            stage="role_resolution",
            code=ErrorCode.TARGET_ROLE_MISSING,
            message=message,
            retryable=False,
        )
        return None, []

    return request.role_profile.role_title, list(request.role_profile.required_skills)


def _courses_from_report(request: CourseRecommendationInput) -> list[Course]:
    return [
        Course(
            code=item.code,
            title=item.title,
            units=item.units,
            section=item.section,
            skills=tuple(item.skills),
            description=item.description,
            prerequisite_text=item.prerequisite_text,
            preclusion_text=item.preclusion_text,
            can_recommend=item.can_recommend,
            source_url=item.source_url,
            offered_terms=tuple(item.offered_terms),
            course_time=item.course_time,
        )
        for item in request.course_catalog
    ]


def _rules_from_report(request: CourseRecommendationInput) -> list[CurriculumRule]:
    return [
        CurriculumRule(
            rule_key=item.rule_key,
            category=item.category,
            intake=item.intake,
            text=item.text,
        )
        for item in request.curriculum_rules
    ]


def _assemble_recommendations(
    picks: list[SelectionPick],
    pool: CandidatePool,
    role_skills: list[str],
) -> tuple[Recommendation, ...]:
    by_code = {course.code: course for course in pool.eligible}
    return tuple(
        {
            "course_code": pick["course_code"],
            "course_title": by_code[pick["course_code"]].title,
            "units": by_code[pick["course_code"]].units,
            "section": by_code[pick["course_code"]].section,
            "offered_terms": list(by_code[pick["course_code"]].offered_terms),
            "course_time": by_code[pick["course_code"]].course_time,
            "priority": pick["priority"],
            "matched_skills": rule_engine.matched_skills_of(
                by_code[pick["course_code"]], role_skills
            ),
            "reason": pick["reason"],
        }
        for pick in picks
    )


def _fallback_picks(
    pool: CandidatePool,
    role_skills: list[str],
    preferences: list[str],
    limit: int,
) -> list[SelectionPick]:
    """Deterministic selection used when the LLM is unavailable — same dict
    shape as the LLM's validated picks."""
    scored = rule_engine.score_candidates(pool, role_skills, preferences, limit)
    picks: list[SelectionPick] = []
    for sc in scored:
        evidence = []
        if sc.matched_gap_skills:
            evidence.append("closes skill gaps: " + ", ".join(sc.matched_gap_skills))
        if sc.matched_role_skills:
            evidence.append(
                "covers role-relevant skills: " + ", ".join(sc.matched_role_skills)
            )
        if sc.matched_preferences:
            evidence.append(
                "matches your interests: " + ", ".join(sc.matched_preferences)
            )
        if not evidence:
            evidence.append("listed in the supplied catalogue as a Core Course")
        picks.append(
            {
                "course_code": sc.course.code,
                "priority": rule_engine.priority_of(sc.score),
                "reason": "; ".join(evidence).capitalize() + ".",
            }
        )
    return picks


def _sources_for(
    recommendations: tuple[Recommendation, ...],
    courses: list[Course],
    evidence_sources: list[str],
) -> tuple[str, ...]:
    """Return only provenance supplied in the report, deduplicated."""
    by_code = {course.code: course for course in courses}
    sources = list(evidence_sources)
    seen = set(sources)
    for rec in recommendations:
        url = by_code[rec["course_code"]].source_url
        if url and url not in seen:
            seen.add(url)
            sources.append(url)
    return tuple(sources)
