"""Course-recommendation orchestration behind the public domain interface.

``CourseRecommendationInput`` is the only data source. User facts, resolved
role skills, the complete course catalogue, curriculum rules, and provenance
must all be supplied by the upstream agent. This module must never retrieve
missing data from a profile store, repository, or knowledge database.

The domain's half of the v3 workflow (S1, S2 and S7 live in the tools
layer): S3 constraints (stages/s3_constraints/), S4 requirement slots
(stages/s4_slots.py), S5 scoring and selection (stages/s5_scoring/). This
module is the conductor — it never implements a rule itself, only
sequences the stages and turns failures into the same "never crash, only
degrade" diagnostics the rest of the app already uses (see errors.py).
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
    ModeInput,
    PlanTerm,
    RecommendationResult,
    RequirementSlot,
    Session,
    SlotPicks,
)
from app.domains.specialist.course_recommendation.policy import curriculum as cs
from app.domains.specialist.course_recommendation.policy import tuning
from app.domains.specialist.course_recommendation.stages import s4_slots
from app.domains.specialist.course_recommendation.stages.s3_constraints import catalog, eligibility
from app.domains.specialist.course_recommendation.stages.s3_constraints import degree_progress as degree_progress_stage
from app.domains.specialist.course_recommendation.stages.s5_scoring import evidence, scorer, selection, signals
from app.domains.specialist.course_recommendation.stages.s6_modes.ad_hoc import AdHoc
from app.domains.specialist.course_recommendation.stages.s6_modes.base import ModeStrategy
from app.domains.specialist.course_recommendation.stages.s6_modes.degree_overview import DegreeOverview

logger = get_logger(__name__)
T = TypeVar("T")

# S6 output modes by name; semester_plan isn't available yet (see _mode_for).
MODES: dict[str, ModeStrategy] = {"degree_overview": DegreeOverview(), "ad_hoc": AdHoc()}


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
            "mode": request.mode,
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
        operation=lambda: degree_progress_stage.compute(
            courses, pool.completed_recognized, pool.completed_units, request.student.capstone_intent,
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
        operation=lambda: s4_slots.derive_slots(
            courses, pool, progress,
            request.role_profile.role_id if request.role_profile else None,
            cs.TRACK_VERTICALS.get(request.student.track_chosen),
        ),
    )
    mode = _mode_for(request, notes, diagnostics)
    if slots:
        # Only the overview shows the electives grouped by Vertical.
        if mode == "degree_overview" and any(s.slot_type == "elective" for s in slots):
            notes.append(
                "Elective groups are organised by Vertical to show each track clearly — the "
                "programme itself only requires the total elective units to be met, however "
                "they are split across Verticals."
            )
        note = _level4000_note(slots, {c.code: c for c in courses}, progress)
        if note:
            notes.append(note)
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
        mode,
        slots,
        {c.code: c for c in courses},
        pool,
        role_skills,
        notes,
        diagnostics,
        stage_results,
    )

    return _assemble_result(
        request, mode, role_title, courses, pool, progress, groups, notes, diagnostics, stage_results
    )


def _mostly_avoided_note(pool: CandidatePool, ctx: signals.ScoringContext) -> str | None:
    """When most eligible courses can only be taken at times the student
    wants kept free (most of the programme meets in the evening), says so:
    avoiding them all would leave little, so they're ranked lower instead."""
    if not pool.eligible or not (ctx.avoid_windows or ctx.avoid_days):
        return None
    hit = sum(1 for course in pool.eligible if signals.forced_avoided_slot(course, ctx))
    if hit * 2 <= len(pool.eligible):
        return None
    return (
        f"{hit} of the {len(pool.eligible)} courses open to you meet at times you want kept free "
        "(much of the programme is taught in the evening), so avoiding them all would leave "
        "few options — they're ranked lower rather than left out."
    )


def _plan_term(request: CourseRecommendationInput) -> PlanTerm | None:
    """The semester being planned, for a semester_plan request."""
    planning = request.planning
    if request.mode != "semester_plan" or planning is None:
        return None
    return PlanTerm(ay=planning.ay, semester=planning.semester, label=planning.label)


def _mode_for(request: CourseRecommendationInput, notes: list[str], diagnostics: list[WorkflowDiagnostic]) -> str:
    """The mode to run: the requested one when it's available."""
    if request.mode in MODES:
        return request.mode
    message = (
        "Planning a single semester isn't available yet, so this is the overall "
        "recommendation for the rest of the degree."
    )
    notes.append(message)
    _add_diagnostic(
        diagnostics,
        request_id=request.request_id,
        stage="slot_selection",
        code=ErrorCode.MODE_NOT_AVAILABLE,
        message=message,
        retryable=False,
    )
    return "degree_overview"


def _process_slots(
    request: CourseRecommendationInput,
    mode: str,
    slots: tuple[RequirementSlot, ...],
    courses_by_code: dict[str, Course],
    pool: CandidatePool,
    role_skills: list[str],
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    stage_results: list[WorkflowStageResult],
) -> list[Group]:
    """S5 (score, then select) and the S6 mode that shapes the result:
    per slot for degree_overview, across all eligible courses for ad_hoc."""
    role = request.role_profile
    wanted = request.constraints
    skill_share = signals.skill_shares(list(courses_by_code.values()))
    scoring_ctx = signals.ScoringContext(
        target_role_tag=role.role_id if role else None,
        role_skills=tuple(role_skills),
        skill_gaps=frozenset(pool.skill_gaps),
        skill_share=skill_share,
        preferences=tuple(wanted.keywords),
        project_averse=wanted.workload_style == "less_project",
        requested_codes=frozenset(wanted.include_codes),
        preferred_skills=tuple(wanted.preferred_skills),
        interest_verticals=frozenset(
            cs.TRACK_VERTICALS[t]
            for t in {*wanted.vertical_preference, *request.student.track_interest}
        ),
        prefers_lecture=wanted.workload_style == "lecture",
        avoid_windows=tuple((w.start, w.end) for w in wanted.avoid_time_windows),
        avoid_days=frozenset(wanted.avoid_days),
        plan_term=(plan_term.ay, plan_term.semester) if (plan_term := _plan_term(request)) else None,
    )
    note = _mostly_avoided_note(pool, scoring_ctx)
    if note:
        notes.append(note)
    evidence_ctx = evidence.EvidenceContext(
        target_role=(role.role_id, role.role_title) if role else None,
        skill_share=skill_share,
        prerequisite_cautions=frozenset(pool.prerequisite_cautions),
    )
    _note_unavailable_requests(wanted.include_codes, pool, courses_by_code, notes)

    if mode == "ad_hoc":
        slot_by_code = {code: slot for slot in slots for code in slot.eligible_candidates}
        scored = scorer.score_slot_candidates(pool.eligible, scoring_ctx)
        top, matched = selection.select_top(scored, slot_by_code, tuning.AD_HOC_TOP_N, evidence_ctx)
        _record_stage(
            stage_results,
            diagnostics,
            stage="slot_selection",
            status="success",
            summary="Scored selection picked the best matches across all eligible courses.",
            output={
                "picked": [pick.scored.course.code for pick in top],
                "matches_request": matched,
            },
            diagnostic_codes=(),
        )
        return MODES[mode].assemble(ModeInput(top_picks=tuple(top), top_matches_request=matched), pool)

    slot_picks: list[SlotPicks] = []

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
            slot_picks.append(SlotPicks(slot=slot, picks=(), note=message))
            continue

        scored = scorer.score_slot_candidates(candidates, scoring_ctx)
        picks = tuple(selection.select_for_slot(slot, scored, evidence_ctx))
        _record_stage(
            stage_results,
            diagnostics,
            stage="slot_selection",
            status="success",
            summary=f"Scored selection filled {slot.label}.",
            output={
                "slot_id": slot.slot_id,
                "picked": [pick.scored.course.code for pick in picks],
                "scores": {pick.scored.course.code: pick.scored.score for pick in picks},
            },
            diagnostic_codes=(),
        )
        slot_picks.append(SlotPicks(slot=slot, picks=picks))

    return MODES[mode].assemble(ModeInput(slot_picks=tuple(slot_picks)), pool)


def _note_unavailable_requests(
    requested: list[str], pool: CandidatePool, courses_by_code: dict[str, Course], notes: list[str],
) -> None:
    """Says why a course the student asked for can't be recommended."""
    eligible = {c.code for c in pool.eligible}
    reasons = {item["course_code"]: item["reason"] for item in pool.excluded_courses}
    wording = {
        "already_completed": "you've already completed it",
        "not_recommendable": "it isn't currently offered in the programme",
        "needs_review": "its course details are still being checked",
        "precluded_by_completed_course": "a course you've completed precludes it",
        "level_not_countable": "its level doesn't count toward the degree",
        "prerequisite_unmet": "its prerequisite isn't completed yet",
        "not_offered_in_term": "it doesn't run in the semester being planned",
    }
    for code in requested:
        if code in eligible:
            continue
        if code not in courses_by_code:
            notes.append(f"{code} isn't in the programme's course catalogue.")
        else:
            why = wording.get(reasons.get(code, ""), "it isn't open to you right now")
            notes.append(f"{code} can't be recommended: {why}.")


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
            request.constraints.exclude_codes, _plan_term(request),
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
    for code in pool.kept_mandatory:
        message = (
            f"{code} is a mandatory core course, so it stays in the recommendation "
            "even though you asked to leave it out."
        )
        notes.append(message)
        _add_diagnostic(
            diagnostics,
            request_id=request_id,
            stage="candidate_pool_building",
            code=ErrorCode.EXCLUDE_MANDATORY,
            message=message,
            retryable=False,
        )
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
    mode: str,
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
        mode=mode,
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


def _level4000_note(
    slots: tuple[RequirementSlot, ...], courses_by_code: dict[str, Course], progress: DegreeProgress
) -> str | None:
    """Points out the 4000-level elective cap when 4000-level courses are
    among the elective candidates (once the cap is reached S4 leaves them
    out, so this only fires while there is room left)."""
    has_level4000 = any(
        courses_by_code[code].level == cs.MIN_COUNTABLE_ELECTIVE_LEVEL
        for slot in slots if slot.slot_type == "elective"
        for code in slot.eligible_candidates if code in courses_by_code
    )
    if not has_level4000:
        return None
    return (
        f"At most {cs.MAX_LEVEL_4000_ELECTIVES} 4000-level electives count toward the degree "
        f"({progress.elective_level4000_used} already used)."
    )


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


def _resolve_role_profile(
    request: CourseRecommendationInput,
    notes: list[str],
    diagnostics: list[WorkflowDiagnostic],
    request_id: str,
) -> tuple[str | None, list[str]]:
    """Use only the role evidence already resolved in the input report."""
    if request.role_profile is None:
        message = (
            "No target role is set, so the courses aren't ranked by career direction."
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
            role_tags=tuple((role.tag, role.name) for role in item.role_tags),
            sessions=tuple(Session(**session.model_dump()) for session in item.sessions),
            prerequisite_groups=tuple(tuple(group) for group in item.prerequisites.all_of),
            corequisite_codes=tuple(item.prerequisites.coreq_any_of),
            prerequisite_unparsed=item.prerequisites.unparsed,
        )
        for item in request.course_catalog
    ]


def compute_degree_progress(catalogue: list[dict], completed_codes: list[str]) -> DegreeProgress:
    """S3 classification + degree progress alone, for a caller that needs only
    the progress numbers a recommendation is built on, not a recommendation.
    `catalogue` items carry just code, units and vertical; completed codes
    not in it are ignored, as in eligibility.build_candidate_pool()."""
    courses = _classify_courses([
        Course(
            code=item["code"], title="", units=item["units"], section="", skills=(), description="",
            prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
            vertical=tuple(item.get("vertical") or ()),
        )
        for item in catalogue
    ])
    units_by_code = {c.code: c.units for c in courses}
    recognized = tuple(code for code in dict.fromkeys(completed_codes) if code in units_by_code)
    return degree_progress_stage.compute(courses, recognized, sum(units_by_code[c] for c in recognized))


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
