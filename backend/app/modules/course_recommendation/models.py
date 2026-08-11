"""Internal domain models for the course_recommendation module — structured
views of the knowledge base's courses / career_roles / course_rules chunks
(see repository.py for how raw chunks are parsed into these)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Course:
    """One catalogue course, parsed from a `course:<code>` chunk."""
    code: str
    title: str
    units: int
    faculty: str
    # Annex A section — "Core Courses", "Capstone Project", one of the three
    # "Vertical #N. ..." elective groups, or "" for referenced-only courses.
    section: str
    # Skill ids (subset of rule_engine.SKILL_IDS), parsed from the chunk's
    # "Skills covered:" trailer.
    skills: tuple[str, ...]
    description: str
    prerequisite_text: str
    preclusion_text: str
    can_recommend: bool
    source_url: str

    @property
    def is_core(self) -> bool:
        return self.section == "Core Courses"


@dataclass(frozen=True)
class CareerRole:
    """One career track, parsed from a `role:<role_id>` chunk. role_id values
    line up 1:1 with the profile module's TARGET_ROLE_VALUES."""
    role_id: str
    role_title: str
    required_skills: tuple[str, ...]


@dataclass(frozen=True)
class CurriculumRule:
    """One Annex A curriculum rule, parsed from a `rule:<key>` chunk."""
    rule_key: str
    category: str  # structure | core | replacement | capstone | elective | cohort
    intake: str
    text: str


@dataclass(frozen=True)
class CandidatePool:
    """Output of the hard eligibility rules (agents/rule_engine.py): every
    course the LLM is ALLOWED to pick from, plus the hard facts computed
    along the way. No ranking implied by `eligible` order."""
    eligible: tuple[Course, ...]
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    excluded_by_preclusion: tuple[tuple[str, str], ...]  # (candidate_code, completed_code)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScoredCourse:
    """A candidate plus the evidence the FALLBACK ranking scored it on —
    only used when the LLM selector is unavailable."""
    course: Course
    score: float
    matched_gap_skills: tuple[str, ...]
    matched_role_skills: tuple[str, ...]
    matched_preferences: tuple[str, ...]
    prerequisite_met_by: tuple[str, ...]  # completed codes appearing in its prerequisite text


@dataclass(frozen=True)
class RecommendationResult:
    """What service.recommend_courses() returns to api.py / interface.py."""
    target_role: str | None
    recommendations: tuple[dict, ...]  # api-shaped dicts, see service.py
    skill_gaps: tuple[str, ...]
    completed_recognized: tuple[str, ...]
    completed_unrecognized: tuple[str, ...]
    completed_units: int
    notes: tuple[str, ...]
    sources: tuple[str, ...]
