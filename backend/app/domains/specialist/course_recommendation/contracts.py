"""The sole data boundary between the upstream agent and course recommendation.

The upstream agent must place user context, role evidence, the course
catalogue, and curriculum rules in one report. The recommendation domain is
therefore able to run without reading a profile store or knowledge database.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SchemaVersion = Literal["3.0"]
# The kind of advice asked for: grouped by degree requirement, courses
# matching something specific, or a plan for one semester.
Mode = Literal["degree_overview", "ad_hoc", "semester_plan"]
# The elective Verticals, by the profile's track keys (see
# policy/curriculum.TRACK_VERTICALS for their catalogue names).
TrackId = Literal[
    "computing_technologies",
    "financial_data_analytics_intelligence",
    "digital_financial_transactions_risk",
]
WorkloadStyle = Literal["less_project", "lecture"]
CapstoneIntent = Literal["capstone_research", "capstone_internship", "electives_instead"]
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

ShortText = Annotated[str, Field(max_length=100)]
LongText = Annotated[str, Field(max_length=300)]
EvidenceSource = Annotated[str, Field(max_length=2048)]

_COURSE_CODE = re.compile(r"^[A-Z]{2,4}\d{4}[A-Z]?$")


class _StrictInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _deduplicate_text(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _normalize_completed_courses(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in _deduplicate_text(values):
        upper = value.upper()
        normalized.append(upper if _COURSE_CODE.fullmatch(upper) else value)
    return normalized


def _normalize_candidate_codes(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in _deduplicate_text(values):
        code = value.upper()
        if not _COURSE_CODE.fullmatch(code):
            raise ValueError(f"Invalid candidate course code: {value}")
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized


def _deduplicate_skills(values: list[SkillId]) -> list[SkillId]:
    return list(dict.fromkeys(values))


class GoalInput(_StrictInputModel):
    target_role: LongText | None = None


class BackgroundInput(_StrictInputModel):
    academic_background: LongText | None = None
    tech_level: LongText | None = None
    # An empty list explicitly means that no completed course was reported.
    # The recommendation domain never fills this field from another source.
    completed_courses: list[LongText] = Field(default_factory=list, max_length=50)

    @field_validator("completed_courses")
    @classmethod
    def normalize_completed_courses(cls, value: list[str]) -> list[str]:
        return _normalize_completed_courses(value)


class StudentInput(_StrictInputModel):
    """Study-plan facts about the student (profile, or stated this turn)."""

    capstone_intent: CapstoneIntent | None = None
    track_interest: list[TrackId] = Field(default_factory=list, max_length=3)
    # The Vertical the student has declared (school records).
    track_chosen: TrackId | None = None


class RecommendationConstraints(_StrictInputModel):
    """What this request asks for. Everything here but exclude_codes and
    candidate_course_codes only steers scoring — never a hard filter."""

    # Restricts the candidates to these courses (a caller-supplied scope).
    candidate_course_codes: list[ShortText] | None = Field(default=None, max_length=100)
    # Courses the student asked for / asked not to take. An excluded course
    # is never recommended, except a mandatory one, which stays with a note.
    include_codes: list[ShortText] = Field(default_factory=list, max_length=10)
    exclude_codes: list[ShortText] = Field(default_factory=list, max_length=10)
    preferred_skills: list[SkillId] = Field(default_factory=list, max_length=10)
    keywords: list[ShortText] = Field(default_factory=list, max_length=10)
    vertical_preference: list[TrackId] = Field(default_factory=list, max_length=3)
    workload_style: WorkloadStyle | None = None

    @field_validator("candidate_course_codes")
    @classmethod
    def normalize_candidate_codes(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalize_candidate_codes(value)

    @field_validator("include_codes", "exclude_codes")
    @classmethod
    def normalize_codes(cls, value: list[str]) -> list[str]:
        return _normalize_candidate_codes(value)

    @field_validator("preferred_skills")
    @classmethod
    def deduplicate_skills(cls, value: list[SkillId]) -> list[SkillId]:
        return _deduplicate_skills(value)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        return _deduplicate_text(value)


class RoleProfileInput(_StrictInputModel):
    """Role evidence already resolved by the upstream agent."""

    role_id: ShortText
    role_title: LongText
    required_skills: list[SkillId] = Field(min_length=1, max_length=10)

    @field_validator("required_skills")
    @classmethod
    def deduplicate_skills(cls, value: list[SkillId]) -> list[SkillId]:
        return _deduplicate_skills(value)


DataQuality = Literal["clean", "needs_review"]


class RoleTagInput(_StrictInputModel):
    """A role family a course is tagged for (knowledge.course_tags)."""

    tag: ShortText
    name: LongText


class CourseCatalogItemInput(_StrictInputModel):
    """One complete course record supplied by the upstream agent."""

    code: ShortText
    title: LongText
    units: int = Field(ge=0, le=40)
    section: LongText = ""
    skills: list[SkillId] = Field(default_factory=list, max_length=10)
    description: str = Field(default="", max_length=5000)
    prerequisite_text: str = Field(default="", max_length=3000)
    preclusion_text: str = Field(default="", max_length=3000)
    can_recommend: bool
    # Optional verified display data from the upstream agent. These fields
    # must never be guessed or fetched by this domain itself.
    offered_terms: list[ShortText] = Field(default_factory=list, max_length=20)
    course_time: LongText | None = None
    source_url: str = Field(default="", max_length=2048)
    # NUSMods [lecture, tutorial, lab, project, preparation] hours/week, or
    # None when not supplied — never inferred or estimated by this domain.
    workload: list[float] | None = Field(default=None, min_length=5, max_length=5)
    # "needs_review" flags a course whose catalogue data is still being
    # verified upstream (see knowledge.courses.needs_review) — a data-
    # quality signal, distinct from can_recommend (whether it's part of
    # the programme at all). Defaults to "clean" so older/partial reports
    # from a caller that doesn't know about this field still validate.
    data_quality: DataQuality = "clean"
    # Elective-vertical membership (knowledge.course_electives), e.g.
    # ["Vertical #1. Computing Technologies"]. Empty for a course that is
    # not a vertical elective (core, mandatory, Capstone). Drives S4's
    # requirement-slot derivation — never inferred by this domain.
    vertical: list[ShortText] = Field(default_factory=list, max_length=5)
    corequisite_text: str = Field(default="", max_length=3000)
    # The role families the course is tagged for, as supplied — the direct
    # course-to-role link, used to explain a recommendation (unlike
    # `skills`, which are derived from these tags and much coarser).
    role_tags: list[RoleTagInput] = Field(default_factory=list, max_length=12)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.upper()
        if not _COURSE_CODE.fullmatch(code):
            raise ValueError(f"Invalid course code: {value}")
        return code

    @field_validator("skills")
    @classmethod
    def deduplicate_skills(cls, value: list[SkillId]) -> list[SkillId]:
        return _deduplicate_skills(value)

    @field_validator("offered_terms")
    @classmethod
    def clean_offered_terms(cls, value: list[str]) -> list[str]:
        return _deduplicate_text(value)


class CurriculumRuleInput(_StrictInputModel):
    """One curriculum rule selected and supplied by the upstream agent."""

    rule_key: LongText
    category: ShortText
    intake: ShortText
    text: str = Field(min_length=1, max_length=5000)


class CourseRecommendationInput(_StrictInputModel):
    """The only object the course-recommendation domain may consume."""

    schema_version: SchemaVersion = "3.0"
    request_id: str = Field(
        default_factory=lambda: uuid4().hex, min_length=1, max_length=100
    )
    # Correlation metadata only. The recommendation domain must never use it
    # to retrieve profile or course data.
    user_id: str | None = Field(default=None, min_length=1, max_length=100)
    mode: Mode = "degree_overview"
    goals: GoalInput = Field(default_factory=GoalInput)
    background: BackgroundInput = Field(default_factory=BackgroundInput)
    student: StudentInput = Field(default_factory=StudentInput)
    constraints: RecommendationConstraints = Field(
        default_factory=RecommendationConstraints
    )
    role_profile: RoleProfileInput | None = None
    course_catalog: list[CourseCatalogItemInput] = Field(min_length=1, max_length=500)
    # Reference only: the rules the domain enforces are policy/curriculum.py.
    curriculum_rules: list[CurriculumRuleInput] = Field(default_factory=list, max_length=100)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "CourseRecommendationInput":
        has_role = bool(self.goals.target_role and self.goals.target_role.strip())
        if has_role and self.role_profile is None:
            raise ValueError(
                "role_profile is required when goals.target_role is supplied"
            )
        if not has_role and self.role_profile is not None:
            raise ValueError(
                "goals.target_role is required when role_profile is supplied"
            )

        codes = [course.code for course in self.course_catalog]
        if len(codes) != len(set(codes)):
            raise ValueError("course_catalog contains duplicate course codes")
        return self

    @field_validator("evidence_sources")
    @classmethod
    def clean_evidence_sources(cls, value: list[str]) -> list[str]:
        return _deduplicate_text(value)
