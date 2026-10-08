"""Internal course-recommendation models materialized from the Agent report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from app.domains.specialist.course_recommendation.errors import (
    WorkflowDiagnostic,
    WorkflowStageResult,
)

# Which degree requirement a course would count towards. Computed by
# stages/s3_constraints/catalog.py — never supplied by the upstream report, since that
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

# The four kinds of recommendation group S4 can open, plus the single
# list the ad_hoc mode returns.
SlotType = Literal["core_mandatory", "core_choice", "elective", "capstone", "ad_hoc"]

Mode = Literal["degree_overview", "ad_hoc", "semester_plan"]

CapstonePath = Literal[
    "undecided",
    # The student intends to do the Capstone but isn't ready for it yet.
    "direct_planned",
    "direct_in_progress",
    "direct_completed",
    "elective_alternative_in_progress",
    "elective_alternative_complete",
]


class ScoreBreakdownItem(TypedDict):
    """One scoring signal's contribution, as returned with a recommendation."""

    signal: str
    delta: float
    evidence: str


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
    score_breakdown: list[ScoreBreakdownItem]
    # What the course teaches (its description's opening sentences) and
    # checkable facts for why it fits — see stages/s5_scoring/evidence.py.
    synopsis: str
    evidence: list[str]
    # The requirement group the course counts toward (ad_hoc mode only:
    # there the list isn't grouped by requirement); None when it counts
    # toward none still open.
    counts_toward: str | None


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
        "level_not_countable",
        "excluded_by_student",
    ]
    related_course_code: str


@dataclass(frozen=True)
class Course:
    """One catalogue course materialized from the upstream-Agent report,
    enriched in S3 with requirement_role/level/workload_shape."""

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
    # (tag, display name) of each role family the course is tagged for.
    role_tags: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    # Populated by stages/s3_constraints/catalog.py during S3 — never read before
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
    """Output of S3's hard eligibility rules (stages/s3_constraints/eligibility.py):
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
    # exclusion (see stages/s3_constraints/eligibility.py's module docstring for why).
    prerequisite_cautions: tuple[str, ...] = field(default_factory=tuple)
    # Mandatory courses the student asked to leave out, kept because the
    # degree requires them.
    kept_mandatory: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DegreeProgress:
    """S3's numeric ground truth — the ONE source of truth every later
    stage (slot derivation, scoring) reads instead of re-deriving quota
    state itself."""

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
    # True when capstone_path follows the student's stated intent rather
    # than being inferred from completed units.
    capstone_from_intent: bool = False


@dataclass(frozen=True)
class RequirementSlot:
    """One open recommendation group derived in S4, before S5
    scores and selects within it.

    `required_pick_count` is how many of this slot's picks actually count
    toward the degree requirement — it can be 0 for a Vertical elective
    slot that isn't the one currently carrying the shared elective quota
    (see s4_slots.py's primary/secondary split), in which case
    every recommendation shown is a browsable, non-binding option.
    `display_count` (>= required_pick_count, capped by how many eligible
    candidates actually exist) is how many candidates S5 actually
    shows — always a few more than strictly required so the student has
    real choice instead of one pre-made decision."""

    slot_id: str
    slot_type: SlotType
    label: str
    required_pick_count: int
    display_count: int
    eligible_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ScoreItem:
    """One scoring signal's contribution to a course's score (see
    stages/s5_scoring/signals.py) — `evidence` is user-readable and becomes
    part of the recommendation's reason."""

    signal: str
    delta: float
    evidence: str


@dataclass(frozen=True)
class ScoredCourse:
    """A slot candidate plus the evidence it was scored on. `score` is
    always the sum of `breakdown`'s deltas."""

    course: Course
    score: float
    matched_gap_skills: tuple[str, ...]
    matched_role_skills: tuple[str, ...]
    matched_preferences: tuple[str, ...]
    role_tag_match: bool
    workload_note: str | None = None
    breakdown: tuple[ScoreItem, ...] = field(default_factory=tuple)

    @property
    def matched_skills(self) -> list[str]:
        """The course's skills that matter for the target role (gap skills
        are role skills too), in the course's own order."""
        relevant = set(self.matched_gap_skills) | set(self.matched_role_skills)
        return [s for s in self.course.skills if s in relevant]


@dataclass(frozen=True)
class Pick:
    """One course selected for a requirement slot, with its reason — the
    first `required_pick_count` of a slot's picks are its recommendation,
    the rest browsable alternatives."""

    scored: ScoredCourse
    reason: str
    synopsis: str = ""
    evidence: tuple[str, ...] = field(default_factory=tuple)
    # The slot the course counts toward, when the picks aren't drawn from
    # one slot (ad_hoc mode).
    slot: "RequirementSlot | None" = None


@dataclass(frozen=True)
class SlotPicks:
    """One requirement slot with its S5 picks, handed to the S6 mode.
    `picks` is empty and `note` says why when the slot had no candidates."""

    slot: RequirementSlot
    picks: tuple[Pick, ...]
    note: str | None = None


@dataclass(frozen=True)
class ModeInput:
    """What S5 selected, handed to the S6 mode: each open slot with its
    picks (degree_overview), and the top picks across all slots with
    whether they match what the student asked for (ad_hoc). A workflow
    fills only what the chosen mode reads."""

    slot_picks: tuple[SlotPicks, ...] = ()
    top_picks: tuple[Pick, ...] = ()
    top_matches_request: bool = True


@dataclass(frozen=True)
class RecommendationResult:
    """What workflow.recommend_courses() returns to api.py / interface.py."""

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
    mode: Mode = "degree_overview"
    diagnostics: tuple[WorkflowDiagnostic, ...] = field(default_factory=tuple)
    stage_results: tuple[WorkflowStageResult, ...] = field(default_factory=tuple)
