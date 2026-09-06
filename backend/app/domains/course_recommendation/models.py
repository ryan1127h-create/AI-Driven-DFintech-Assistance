"""Internal course-recommendation models materialized from the Agent report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from app.domains.course_recommendation.errors import (
    WorkflowDiagnostic,
    WorkflowStageResult,
)

Priority = Literal["high", "medium", "low"]


class SelectionPick(TypedDict):
    """Validated model/fallback selection before catalogue facts are attached."""

    course_code: str
    priority: Priority
    reason: str


class Recommendation(TypedDict):
    """One fully assembled recommendation returned by the domain service."""

    course_code: str
    course_title: str
    units: int
    section: str
    offered_terms: list[str]
    course_time: str | None
    priority: Priority
    matched_skills: list[str]
    reason: str


class ExcludedCourse(TypedDict, total=False):
    """A course removed by a hard rule, with its machine-readable reason."""

    course_code: str
    reason: Literal[
        "already_completed",
        "not_recommendable",
        "precluded_by_completed_course",
    ]
    related_course_code: str


@dataclass(frozen=True)
class Course:
    """One catalogue course materialized from the upstream-Agent report."""

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

    @property
    def is_core(self) -> bool:
        return self.section == "Core Courses"


@dataclass(frozen=True)
class CurriculumRule:
    """One curriculum rule materialized from the upstream-Agent report."""

    rule_key: str
    category: str
    intake: str
    text: str


@dataclass(frozen=True)
class CandidatePool:
    """Output of the hard eligibility rules (rule_engine.py): every course
    the LLM is ALLOWED to pick from, plus the hard facts computed along the
    way. No ranking implied by `eligible` order."""

    eligible: tuple[Course, ...]
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    notes: tuple[str, ...] = field(default_factory=tuple)
    excluded_courses: tuple[ExcludedCourse, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScoredCourse:
    """A candidate plus the evidence the FALLBACK ranking scored it on —
    only used when the LLM selector is unavailable."""

    course: Course
    score: float
    matched_gap_skills: tuple[str, ...]
    matched_role_skills: tuple[str, ...]
    matched_preferences: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationResult:
    """What service.recommend_courses() returns to api.py / interface.py."""

    request_id: str
    target_role: str | None
    recommendations: tuple[Recommendation, ...]
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    notes: tuple[str, ...]
    sources: tuple[str, ...]
    workflow_status: Literal["ok", "degraded"] = "ok"
    diagnostics: tuple[WorkflowDiagnostic, ...] = field(default_factory=tuple)
    stage_results: tuple[WorkflowStageResult, ...] = field(default_factory=tuple)
