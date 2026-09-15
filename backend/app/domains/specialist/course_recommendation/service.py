"""Course-recommendation orchestration behind the public domain interface.

``CourseRecommendationInput`` is the only data source. User facts, resolved
role skills, the complete course catalogue, curriculum rules, and provenance
must all be supplied by the upstream agent. This module must never retrieve
missing data from a profile store, repository, or knowledge database.

Runs the 6-STAGE workflow confirmed in the workflow diagrams, delegating
each STAGE's concrete logic to pipeline/: STAGE 2 (catalog.py + eligibility.py),
STAGE 3 (degree_progress.py), STAGE 4 (requirement_slots.py), STAGE 5
(scoring.py + selection.py). This module is the conductor — it never
implements a rule itself, only sequences the pipeline and turns failures
into the same "never crash, only degrade" diagnostics the rest of the app
already uses (see errors.py).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, TypeVar

from app.core.logging import get_logger
from app.domains.specialist.course_recommendation.contracts import CourseRecommendationInput
from app.domains.specialist.course_recommendation.errors import (
    CourseRecommendationStageError,
    ErrorCode,
    StageName,
    StageStatus,
    WorkflowDiagnostic,
    WorkflowStageResult,
)
from app.domains.specialist.course_recommendation.models import (
    CandidatePool,
    Course,
    CurriculumRule,
    DegreeProgress,
    Group,
    Recommendation,
    RecommendationResult,
    RequirementSlot,
)
from app.domains.specialist.course_recommendation.pipeline import (
    catalog,
    degree_progress as degree_progress_pipeline,
    eligibility,
    requirement_slots,
    scoring,
    selection,
)

logger = get_logger(__name__)
T = TypeVar("T")


def recommend_courses(request: CourseRecommendationInput) -> RecommendationResult:
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

    role_title, role_skills = _run_required_stage(
        request_id=request.request_id,
        stage="role_resolution",
        code=ErrorCode.ROLE_RESOLUTION_FAILED,
        message="The role profile supplied in the report could not be resolved.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _resolve_role_profile(request, notes, diagnostics, request.request_id),
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
        message="The course catalogue supplied in the report could not be materialized.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _courses_from_report(request),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="course_catalog_materialization",
        summary="The supplied course catalogue was materialized.",
        output={"course_count": len(courses), "course_codes": [c.code for c in courses]},
    )

    courses = _run_required_stage(
        request_id=request.request_id,
        stage="catalog_classification",
        code=ErrorCode.CATALOG_CLASSIFICATION_FAILED,
        message="The course catalogue could not be classified against the curriculum structure.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _classify_courses(courses),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="catalog_classification",
        summary="Every course was classified by requirement role, level, and workload shape.",
        output={
            "requirement_roles": {c.code: c.requirement_role for c in courses},
        },
    )

    rules = _run_required_stage(
        request_id=request.request_id,
        stage="curriculum_rules_materialization",
        code=ErrorCode.CURRICULUM_RULES_INVALID,
        message="The curriculum rules supplied in the report could not be materialized.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _rules_from_report(request),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="curriculum_rules_materialization",
        summary="The supplied curriculum rules were materialized.",
        output={"rule_count": len(rules)},
    )

    pool = _build_scoped_pool(request, courses, role_skills, notes, diagnostics, stage_results)

    progress = _run_required_stage(
        request_id=request.request_id,
        stage="degree_progress_computation",
        code=ErrorCode.DEGREE_PROGRESS_FAILED,
        message="Degree progress could not be computed from the supplied report.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: degree_progress_pipeline.compute(
            courses, pool.completed_recognized, pool.completed_units
        ),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="degree_progress_computation",
        summary="Degree progress was computed from the supplied completed-course list.",
        output={
            "core_mandatory_remaining": list(progress.core_mandatory_remaining),
            "core_choice_remaining_count": progress.core_choice_remaining_count,
            "capstone_path": progress.capstone_path,
            "elective_units_done": progress.elective_units_done,
            "elective_units_target": progress.elective_units_target,
        },
    )
    notes.extend(progress.core_replacement_cautions)

    slots = _run_required_stage(
        request_id=request.request_id,
        stage="requirement_slot_derivation",
        code=ErrorCode.SLOT_DERIVATION_FAILED,
        message="Requirement groups could not be derived from degree progress.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: requirement_slots.derive_slots(courses, pool, progress),
    )
    if slots:
        notes.append(
            "Elective groups are organised by Vertical to show each track clearly — the "
            "programme itself only requires the total elective units to be met, however "
            "they are split across Verticals."
        )
    else:
        message = (
            "Core and elective requirements appear satisfied based on the supplied "
            "completed-course list; consider a graduation / Capstone status check."
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request.request_id,
            stage="requirement_slot_derivation",
            code=ErrorCode.NO_OPEN_SLOTS,
            message=message,
            retryable=False,
        )
    _record_stage(
        stage_results,
        diagnostics,
        stage="requirement_slot_derivation",
        summary="Open requirement groups were derived from degree progress.",
        output={
            "slot_count": len(slots),
            "slots": [
                {"slot_id": s.slot_id, "slot_type": s.slot_type, "pick_count": s.required_pick_count}
                for s in slots
            ],
        },
    )

    groups = _process_slots(
        request,
        slots,
        {c.code: c for c in courses},
        pool,
        role_title,
        role_skills,
        diagnostics,
        stage_results,
    )

    return _assemble_result(
        request, role_title, courses, pool, progress, groups, notes, diagnostics, stage_results
    )


def _process_slots(
    request: CourseRecommendationInput,
    slots: tuple[RequirementSlot, ...],
    courses_by_code: dict[str, Course],
    pool: CandidatePool,
    role_title: str | None,
    role_skills: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> list[Group]:
    preferences = _preference_keywords(request)
    project_averse = catalog.is_project_averse(request.preferences.acceptable_workload)
    student_context = _student_context(request)
    groups: list[Group] = []

    for slot in slots:
        candidates = tuple(
            courses_by_code[code] for code in slot.eligible_candidates if code in courses_by_code
        )
        if not candidates:
            message = f"No eligible candidates are currently available for {slot.label}."
            _add_diagnostic(
                diagnostics,
                request_id=request.request_id,
                stage="slot_selection",
                code=ErrorCode.SLOT_NO_CANDIDATES,
                message=message,
                retryable=False,
            )
            _record_stage(
                stage_results,
                diagnostics,
                stage="slot_selection",
                status="skipped",
                summary=f"Slot {slot.slot_id} skipped: no eligible candidates.",
                output={"slot_id": slot.slot_id, "reason": "no_candidates"},
            )
            groups.append(_empty_group(slot, message))
            continue

        scored = scoring.score_slot_candidates(
            candidates, role_skills, pool.skill_gaps, preferences,
            request.curated_role_courses, project_averse,
        )
        group = _select_slot_group(
            request, slot, scored, role_title, role_skills, pool, student_context,
            diagnostics, stage_results,
        )
        groups.append(group)

    return groups


def _select_slot_group(
    request: CourseRecommendationInput,
    slot: RequirementSlot,
    scored: list,
    role_title: str | None,
    role_skills: list[str],
    pool: CandidatePool,
    student_context: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> Group:
    try:
        outcome = selection.select_for_slot(
            slot, scored, role_title, student_context, request_id=request.request_id
        )
    except Exception:
        logger.exception(
            "unexpected slot selection failure request_id=%s slot=%s",
            request.request_id,
            slot.slot_id,
        )
        outcome = selection.SlotSelectionOutcome(
            picks=None,
            error_code=ErrorCode.SLOT_LLM_SELECTION_FAILED,
            error_message="The course-selection stage failed unexpectedly for this group.",
            retryable=True,
        )

    if outcome.picks is not None:
        _record_stage(
            stage_results,
            diagnostics,
            stage="slot_selection",
            summary=f"The LLM selector filled {slot.label}.",
            output={
                "slot_id": slot.slot_id,
                "model_invoked": True,
                "attempts": outcome.attempts,
                "picked": [p["course_code"] for p in outcome.picks],
            },
        )
        picks = list(outcome.picks)
        slot_note = "; ".join(outcome.notes) or None
    else:
        code = outcome.error_code or ErrorCode.SLOT_LLM_SELECTION_FAILED
        _add_diagnostic(
            diagnostics,
            request_id=request.request_id,
            stage="slot_selection",
            code=code,
            message=outcome.error_message or "The model selector could not fill this group.",
            retryable=outcome.retryable,
        )
        picks = selection.fallback_for_slot(slot, scored)
        _record_stage(
            stage_results,
            diagnostics,
            stage="slot_selection",
            status="degraded",
            summary=f"Deterministic fallback filled {slot.label}.",
            output={
                "slot_id": slot.slot_id,
                "model_invoked": True,
                "attempts": outcome.attempts,
                "picked": [p["course_code"] for p in picks],
            },
            diagnostic_codes=(code,),
        )
        slot_note = None
        if not picks:
            fallback_message = f"No suitable candidate could be ranked for {slot.label}."
            _add_diagnostic(
                diagnostics,
                request_id=request.request_id,
                stage="slot_selection",
                code=ErrorCode.SLOT_FALLBACK_EMPTY,
                message=fallback_message,
                retryable=False,
            )
            slot_note = fallback_message

    by_code = {sc.course.code: sc for sc in scored}
    recommendations = [
        _build_recommendation(
            by_code[p["course_code"]], p["reason"], role_skills, pool,
            recommended=index < slot.required_pick_count,
        )
        for index, p in enumerate(picks)
    ]
    if slot.slot_type == "elective" and slot.required_pick_count == 0:
        slot_note = (
            f"{slot_note} {requirement_slots.SECONDARY_VERTICAL_NOTE}"
            if slot_note
            else requirement_slots.SECONDARY_VERTICAL_NOTE
        )
    return {
        "slot_id": slot.slot_id,
        "slot_type": slot.slot_type,
        "label": slot.label,
        "required_pick_count": slot.required_pick_count,
        "recommendations": recommendations,
        "note": slot_note,
    }


def _empty_group(slot: RequirementSlot, note: str) -> Group:
    return {
        "slot_id": slot.slot_id,
        "slot_type": slot.slot_type,
        "label": slot.label,
        "required_pick_count": slot.required_pick_count,
        "recommendations": [],
        "note": note,
    }


def _build_recommendation(
    scored_course, reason: str, role_skills: list[str], pool: CandidatePool, *, recommended: bool
) -> Recommendation:
    course = scored_course.course
    cautions: list[str] = []
    if course.code in pool.prerequisite_cautions:
        cautions.append(
            f"Prerequisite not yet confirmed among completed courses: {course.prerequisite_text}"
        )
    if course.corequisite_text:
        cautions.append(f"Corequisite: {course.corequisite_text}")
    if scored_course.workload_note:
        cautions.append(scored_course.workload_note)

    return {
        "course_code": course.code,
        "course_title": course.title,
        "units": course.units,
        "section": course.section,
        "vertical": list(course.vertical),
        "level": course.level,
        "offered_terms": list(course.offered_terms),
        "course_time": course.course_time,
        "workload": list(course.workload) if course.workload is not None else None,
        "matched_skills": scoring.matched_skills_of(course, role_skills),
        "reason": reason,
        "recommended": recommended,
        "caution": " | ".join(cautions) or None,
    }


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
        operation=lambda: eligibility.build_candidate_pool(
            courses, request.background.completed_courses, role_skills,
        ),
    )
    _record_pool_diagnostics(pool, notes, diagnostics, request.request_id)
    _record_stage(
        stage_results,
        diagnostics,
        stage="candidate_pool_building",
        summary="Hard eligibility rules produced the candidate pool.",
        output={
            "eligible_course_codes": [c.code for c in pool.eligible],
            "excluded_courses": list(pool.excluded_courses),
            "prerequisite_cautions": list(pool.prerequisite_cautions),
            "skill_gaps": list(pool.skill_gaps),
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
            pool, request.constraints.candidate_course_codes, courses, notes, diagnostics,
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


def _assemble_result(
    request: CourseRecommendationInput,
    role_title: str | None,
    courses: list[Course],
    pool: CandidatePool,
    progress: DegreeProgress,
    groups: list[Group],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> RecommendationResult:
    """Attach sources and workflow diagnostics to the final grouped result."""
    _record_stage(
        stage_results,
        diagnostics,
        stage="result_assembly",
        summary="Group results were merged into the final recommendation.",
        output={"group_count": len(groups)},
    )
    sources = _run_required_stage(
        request_id=request.request_id,
        stage="source_assembly",
        code=ErrorCode.SOURCE_ASSEMBLY_FAILED,
        message="The recommendation sources could not be assembled.",
        retryable=False,
        stage_results=stage_results,
        operation=lambda: _sources_for(groups, courses, request.evidence_sources),
    )
    _record_stage(
        stage_results,
        diagnostics,
        stage="source_assembly",
        summary="Evidence sources were assembled and deduplicated.",
        output={"source_count": len(sources)},
    )

    return RecommendationResult(
        request_id=request.request_id,
        target_role=role_title,
        groups=tuple(groups),
        degree_progress=progress,
        skill_gaps=pool.skill_gaps,
        completed_recognized=pool.completed_recognized,
        completed_unrecognized=pool.completed_unrecognized,
        completed_units=pool.completed_units,
        notes=tuple(notes),
        sources=sources,
        workflow_status="degraded" if diagnostics else "ok",
        diagnostics=tuple(diagnostics),
        stage_results=tuple(stage_results),
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
        WorkflowDiagnostic(stage=stage, code=code, message=message, retryable=retryable)
    )
    logger.warning(
        "course recommendation degraded request_id=%s stage=%s code=%s",
        request_id,
        stage,
        code,
    )


def _preference_keywords(request: CourseRecommendationInput) -> list[str]:
    """Preference text used by STAGE 5 scoring."""
    values = [*request.preferences.course_styles, *request.preferences.other_preferences]
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
            workload=tuple(item.workload) if item.workload is not None else None,
            data_quality=item.data_quality,
            vertical=tuple(item.vertical),
            corequisite_text=item.corequisite_text,
        )
        for item in request.course_catalog
    ]


def _classify_courses(courses: list[Course]) -> list[Course]:
    return [
        replace(
            course,
            requirement_role=catalog.classify_requirement_role(course.code, course.vertical),
            level=catalog.course_level(course.code),
            workload_shape=catalog.workload_shape_of(course.workload),
        )
        for course in courses
    ]


def _rules_from_report(request: CourseRecommendationInput) -> list[CurriculumRule]:
    return [
        CurriculumRule(
            rule_key=item.rule_key, category=item.category, intake=item.intake, text=item.text,
        )
        for item in request.curriculum_rules
    ]


def _sources_for(
    groups: list[Group],
    courses: list[Course],
    evidence_sources: list[str],
) -> tuple[str, ...]:
    """Return only provenance supplied in the report, deduplicated."""
    by_code = {course.code: course for course in courses}
    sources = list(evidence_sources)
    seen = set(sources)
    for group in groups:
        for rec in group["recommendations"]:
            url = by_code[rec["course_code"]].source_url
            if url and url not in seen:
                seen.add(url)
                sources.append(url)
    return tuple(sources)
