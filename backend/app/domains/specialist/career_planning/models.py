"""Internal career-planning models: what each stage hands the next."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# met: the evidence shows the skill; partial: some evidence, not enough;
# missing: the profile says it isn't there; unknown: no evidence either way.
SkillStatus = Literal["met", "partial", "missing", "unknown"]

# A profile fact as S3 reads it: a level, a single value, or several.
FactValue = int | str | tuple[str, ...]


@dataclass(frozen=True)
class FunctionExperience:
    key: str
    internship: bool = False


@dataclass(frozen=True)
class StudentEvidence:
    """The student's evidence-bearing facts, materialized from the report's
    profile section: `facts` by field key (only fields on file), the
    functional experience, and the courses from the student record."""

    facts: dict[str, FactValue] = field(default_factory=dict)
    functions: tuple[FunctionExperience, ...] = ()
    completed_courses: tuple[str, ...] = ()
    current_courses: tuple[str, ...] = ()


@dataclass(frozen=True)
class CourseLink:
    """A programme course and the role families it is tagged for."""

    code: str
    title: str
    tags: frozenset[str]


@dataclass(frozen=True)
class EvidenceItem:
    """One fact that counted toward a skill: a profile field and the
    value(s) that matched, or the courses ("courses") that did."""

    source: str
    values: tuple[str, ...]
    points: float
    # Courses still being taken / experience gained only as an intern.
    in_progress: bool = False
    internship: bool = False


@dataclass(frozen=True)
class SkillAssessment:
    skill: str
    status: SkillStatus
    # Summed evidence points, capped at policy.skill_evidence.MET_POINTS.
    points: float
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class CareerPlanResult:
    target_role: str
    current_fit: str
    skill_assessment: tuple[dict, ...]
    phases: tuple[dict, ...]
    success_indicators: tuple[str, ...]
    notes: tuple[str, ...]
    sources: tuple[str, ...]
