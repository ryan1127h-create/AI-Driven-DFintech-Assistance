"""Internal course-recommendation models materialized from the Agent report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from app.domains.specialist.course_recommendation.errors import (
    WorkflowDiagnostic,
    WorkflowStageResult,
)

# Which degree requirement a course would count towards. Computed by
# pipeline/catalog.py — never supplied by the upstream report, since that
# would require the report assembler to know NUS curriculum policy, which
# is exactly what this domain is meant to encapsulate.
RequirementRole = Literal[
    "core_mandatory",
    "core_choice",
    "elective",
    "capstone",
    "core_replacement_candidate",
    "unclassified",
]

# Which kind of weekly effort a course demands, derived from its NUSMods
# workload 5-tuple. None when workload data is unavailable.
WorkloadShape = Literal["lecture_heavy", "project_heavy", "balanced"]

# The four kinds of recommendation group STAGE 4 can open.
SlotType = Literal["core_mandatory", "core_choice", "elective", "capstone"]

CapstonePath = Literal[
    "undecided",
    "direct_in_progress",
    "direct_completed",
    "elective_alternative_in_progress",
    "elective_alternative_complete",
]


class SelectionPick(TypedDict):
    """One validated model/fallback selection for a single requirement slot,
    before catalogue facts are attached."""

    course_code: str
    reason: str


class Recommendation(TypedDict):
    """One fully assembled recommendation returned within a group. A group
    shows more candidates than are strictly required (see RequirementSlot
    .display_count) so the student has real choice — `recommended` marks
    which ones are the top pick(s) versus a browsable alternative."""

    course_code: str
    course_title: str
    units: int
    section: str
    vertical: list[str]
    level: int | None
    offered_terms: list[str]
    course_time: str | None
    workload: list[float] | None
    matched_skills: list[str]
    reason: str
    caution: str | None
    recommended: bool


class Group(TypedDict):
    """One requirement-driven recommendation group ("Group A/B/C..." in the
    confirmed design) — the unit of output this redesign exists to produce,
    replacing the old flat top-N list."""

    slot_id: str
    slot_type: SlotType
    label: str
    required_pick_count: int
    recommendations: list[Recommendation]
    note: str | None


class ExcludedCourse(TypedDict, total=False):
    """A course removed by a hard rule, with its machine-readable reason."""

    course_code: str
    reason: Literal[
        "already_completed",
        "not_recommendable",
        "precluded_by_completed_course",
        "needs_review",
    ]
    related_course_code: str


@dataclass(frozen=True)
class Course:
    """One catalogue course materialized from the upstream-Agent report,
    enriched in STAGE 2 with requirement_role/level/workload_shape."""

    code: str
    title: str
    units: int
    section: str
    skills: tuple[str, ...]
    description: str
    prerequisite_text: str
    preclusion_text: str
    can_recommend: bool
    source_url: str
    offered_terms: tuple[str, ...] = field(default_factory=tuple)
    course_time: str | None = None
    workload: tuple[float, ...] | None = None
    data_quality: Literal["clean", "needs_review"] = "clean"
    vertical: tuple[str, ...] = field(default_factory=tuple)
    corequisite_text: str = ""
    # Populated by pipeline/catalog.py during STAGE 2 — never read before
    # that stage runs, so default to the safe "not yet classified" values.
    requirement_role: RequirementRole = "unclassified"
    level: int | None = None
    workload_shape: WorkloadShape | None = None


@dataclass(frozen=True)
class CurriculumRule:
    """One curriculum rule materialized from the upstream-Agent report."""

    rule_key: str
    category: str
    intake: str
    text: str


@dataclass(frozen=True)
class CandidatePool:
    """Output of STAGE 2's hard eligibility rules (pipeline/eligibility.py):
    every course a requirement slot is ALLOWED to draw from, plus the hard
    facts computed along the way. No ranking implied by `eligible` order."""

    eligible: tuple[Course, ...]
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    notes: tuple[str, ...] = field(default_factory=tuple)
    excluded_courses: tuple[ExcludedCourse, ...] = field(default_factory=tuple)
    # Courses that stayed eligible but whose prerequisite text names a code
    # not found among the student's completed courses — a caution, never an
    # exclusion (see pipeline/eligibility.py's module docstring for why).
    prerequisite_cautions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DegreeProgress:
    """STAGE 3's numeric ground truth — the ONE source of truth every later
    stage (slot derivation, scoring, the LLM prompt) reads instead of
    re-deriving quota state itself."""

    core_mandatory_done: tuple[str, ...]
    core_mandatory_remaining: tuple[str, ...]
    core_choice_done: tuple[str, ...]
    core_choice_remaining_count: int
    core_choice_surplus: tuple[str, ...]
    core_replacement_cautions: tuple[str, ...]
    capstone_path: CapstonePath
    elective_units_done: int
    elective_units_target: int
    elective_level4000_used: int
    elective_level4000_cap_reached: bool
    total_units_done: int
    total_units_target: int


@dataclass(frozen=True)
class RequirementSlot:
    """One open recommendation group derived in STAGE 4, before STAGE 5
    scores and selects within it.

    `required_pick_count` is how many of this slot's picks actually count
    toward the degree requirement — it can be 0 for a Vertical elective
    slot that isn't the one currently carrying the shared elective quota
    (see requirement_slots.py's primary/secondary split), in which case
    every recommendation shown is a browsable, non-binding option.
    `display_count` (>= required_pick_count, capped by how many eligible
    candidates actually exist) is how many candidates STAGE 5 actually
    shows — always a few more than strictly required so the student has
    real choice instead of one pre-made decision."""

    slot_id: str
    slot_type: SlotType
    label: str
    required_pick_count: int
    display_count: int
    eligible_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ScoredCourse:
    """A slot candidate plus the evidence it was scored on — surfaced to the
    LLM prompt and used verbatim by the deterministic fallback."""

    course: Course
    score: float
    matched_gap_skills: tuple[str, ...]
    matched_role_skills: tuple[str, ...]
    matched_preferences: tuple[str, ...]
    curated_match: bool
    workload_note: str | None = None


@dataclass(frozen=True)
class RecommendationResult:
    """What service.recommend_courses() returns to api.py / interface.py."""

    request_id: str
    target_role: str | None
    groups: tuple[Group, ...]
    degree_progress: DegreeProgress | None
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    notes: tuple[str, ...]
    sources: tuple[str, ...]
    workflow_status: Literal["ok", "degraded"] = "ok"
    diagnostics: tuple[WorkflowDiagnostic, ...] = field(default_factory=tuple)
    stage_results: tuple[WorkflowStageResult, ...] = field(default_factory=tuple)
