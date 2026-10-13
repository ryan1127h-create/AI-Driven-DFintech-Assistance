"""The sole data boundary between the upstream agent and career planning.

The upstream agent (the tools layer) places the student's evidence and
situation, the role catalogue and the course-to-role links in one report;
the domain runs on that report alone and never reads a profile store or
the knowledge base.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SchemaVersion = Literal["1.0"]
# The kind of career advice asked for: which roles fit, how to get ready
# for one role, or how two or three roles compare.
Mode = Literal["exploration", "plan", "compare"]
LifecycleStage = Literal["prospect", "applicant", "admitted", "current", "graduating", "alumni"]
# The skill vocabulary of the knowledge base's role tags
# (knowledge.tags_definition.required_skills).
SkillId = Literal[
    "ai_ml",
    "data_analytics",
    "data_engineering",
    "finance",
    "payments_systems",
    "product",
    "programming",
    "regulation",
    "risk_modeling",
    "security",
]
JobSearchTimeline = Literal["during_program", "right_after", "1yr_plus_later", "not_job_seeking"]
InternshipStatus = Literal["none", "searching", "secured", "completed"]
CapstoneIntent = Literal["capstone_research", "capstone_internship", "electives_instead", "undecided"]
# The programme-readiness areas the derived labels rate (profile.derived).
ReadinessArea = Literal["programming", "finance", "maths_stats"]

ShortText = Annotated[str, Field(max_length=100)]
LongText = Annotated[str, Field(max_length=500)]
EvidenceSource = Annotated[str, Field(max_length=2048)]

_COURSE_CODE = re.compile(r"^[A-Z]{2,4}\d{4}[A-Z]?$")
_TERM_LABEL = re.compile(r"^AY\d{4}/\d{2} Sem[12]$")


class _StrictInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _course_codes(values: list[str]) -> list[str]:
    codes = []
    for value in values:
        code = value.strip().upper()
        if not _COURSE_CODE.fullmatch(code):
            raise ValueError(f"Invalid course code: {value}")
        codes.append(code)
    return _deduplicate(codes)


class FunctionExperienceInput(_StrictInputModel):
    """One line of work the student has done (profile function_experience);
    `internship` marks experience gained only as an intern."""

    key: ShortText
    internship: bool = False


class ProfileEvidenceInput(_StrictInputModel):
    """The profile facts skill evidence is read from (see
    policy/skill_evidence.py), as the profile stores them. Absent means
    not on file — never "doesn't have it"."""

    code_level: int | None = Field(default=None, ge=0, le=4)
    ml_ai_level: int | None = Field(default=None, ge=1, le=3)
    data_engineering_level: int | None = Field(default=None, ge=1, le=3)
    blockchain_level: int | None = Field(default=None, ge=1, le=3)
    finance_level: int | None = Field(default=None, ge=1, le=3)
    math_stats_level: int | None = Field(default=None, ge=1, le=3)
    tech_stack: list[ShortText] = Field(default_factory=list, max_length=30)
    domain_knowledge: list[ShortText] = Field(default_factory=list, max_length=20)
    certifications: list[ShortText] = Field(default_factory=list, max_length=20)
    prior_coursework: list[ShortText] = Field(default_factory=list, max_length=20)
    function_experience: list[FunctionExperienceInput] = Field(default_factory=list, max_length=10)
    degree_discipline_category: ShortText | None = None
    total_work_years: ShortText | None = None
    seniority_level: ShortText | None = None
    employment_status: ShortText | None = None
    # Courses from the student record, done and being taken.
    completed_courses: list[ShortText] = Field(default_factory=list, max_length=60)
    current_courses: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("tech_stack", "domain_knowledge", "certifications", "prior_coursework")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)

    @field_validator("completed_courses", "current_courses")
    @classmethod
    def normalize_codes(cls, value: list[str]) -> list[str]:
        return _course_codes(value)


class SituationInput(_StrictInputModel):
    """Where the student is and what they're aiming at — the roadmap's
    anchors."""

    stage: LifecycleStage | None = None
    career_goal_clarity: ShortText | None = None
    program_motivation: ShortText | None = None
    expected_grad_term: ShortText | None = None
    job_search_timeline: JobSearchTimeline | None = None
    internship_status: InternshipStatus | None = None
    capstone_intent: CapstoneIntent | None = None
    target_markets: list[ShortText] = Field(default_factory=list, max_length=9)

    @field_validator("expected_grad_term")
    @classmethod
    def validate_term(cls, value: str | None) -> str | None:
        if value is not None and not _TERM_LABEL.fullmatch(value):
            raise ValueError("expected_grad_term is a term like 'AY2027/28 Sem1'")
        return value

    @field_validator("target_markets")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)


class ReadinessGapInput(_StrictInputModel):
    """A programme-readiness area the student is self-rated below
    (profile.derived readiness_gap with status "gap")."""

    area: ReadinessArea
    level: int = Field(ge=0, le=4)
    required: int = Field(ge=1, le=4)


class RoleDefinitionInput(_StrictInputModel):
    """One role family (knowledge.tags_definition)."""

    tag: ShortText
    name: LongText
    definition: LongText = ""
    required_skills: list[SkillId] = Field(min_length=1, max_length=10)

    @field_validator("required_skills")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)


class CourseLinkInput(_StrictInputModel):
    """A programme course and the role families it is tagged for
    (knowledge.course_tags)."""

    code: ShortText
    title: LongText
    tags: list[ShortText] = Field(min_length=1, max_length=12)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _course_codes([value])[0]


class CareerPlanningInput(_StrictInputModel):
    """The only object the career-planning domain may consume."""

    schema_version: SchemaVersion = "1.0"
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=100)
    # Correlation metadata only; never used to look anything up.
    user_id: str | None = Field(default=None, min_length=1, max_length=100)
    mode: Mode
    # The date the roadmap is planned from.
    today: date
    # The roles this request is about: one for a plan, two or three for a
    # comparison, none for exploration (which considers every role).
    target_roles: list[ShortText] = Field(default_factory=list, max_length=3)
    # Roles the student has listed in their profile; exploration marks them.
    preferred_roles: list[ShortText] = Field(default_factory=list, max_length=12)
    profile: ProfileEvidenceInput = Field(default_factory=ProfileEvidenceInput)
    situation: SituationInput = Field(default_factory=SituationInput)
    readiness_gaps: list[ReadinessGapInput] = Field(default_factory=list, max_length=3)
    role_catalog: list[RoleDefinitionInput] = Field(min_length=1, max_length=50)
    course_links: list[CourseLinkInput] = Field(default_factory=list, max_length=500)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list, max_length=50)

    @field_validator("target_roles", "preferred_roles", "evidence_sources")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "CareerPlanningInput":
        tags = [role.tag for role in self.role_catalog]
        if len(tags) != len(set(tags)):
            raise ValueError("role_catalog contains duplicate role tags")
        known = set(tags)
        unknown = [t for t in (*self.target_roles, *self.preferred_roles) if t not in known]
        if unknown:
            raise ValueError("roles not in role_catalog: " + ", ".join(unknown))
        codes = [link.code for link in self.course_links]
        if len(codes) != len(set(codes)):
            raise ValueError("course_links contains duplicate course codes")
        for link in self.course_links:
            if not set(link.tags) <= known:
                raise ValueError(f"course {link.code} is tagged with a role not in role_catalog")

        count = len(self.target_roles)
        if self.mode == "plan" and count != 1:
            raise ValueError("a plan is for exactly one target role")
        if self.mode == "compare" and count < 2:
            raise ValueError("a comparison needs two or three target roles")
        if self.mode == "exploration" and count:
            raise ValueError("exploration considers every role; target_roles must be empty")
        return self
