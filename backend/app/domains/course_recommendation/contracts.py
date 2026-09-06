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

InputSource = Literal[
    "user_message",
    "profile_db",
    "upstream_agent_inference",
    "default",
]
SchemaVersion = Literal["2.0"]
SkillId = Literal[
    "ai_ml",
    "data_analytics",
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
FieldPath = Annotated[str, Field(max_length=200)]
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
    target_industry: LongText | None = None


class BackgroundInput(_StrictInputModel):
    academic_background: LongText | None = None
    tech_level: LongText | None = None
    school_tier: ShortText | None = None
    work_years: int | None = Field(default=None, ge=0, le=80)
    # An empty list explicitly means that no completed course was reported.
    # The recommendation domain never fills this field from another source.
    completed_courses: list[LongText] = Field(default_factory=list, max_length=50)

    @field_validator("completed_courses")
    @classmethod
    def normalize_completed_courses(cls, value: list[str]) -> list[str]:
        return _normalize_completed_courses(value)


class PreferenceInput(_StrictInputModel):
    acceptable_workload: ShortText | None = None
    course_styles: list[ShortText] = Field(default_factory=list, max_length=10)
    other_preferences: list[ShortText] = Field(default_factory=list, max_length=10)

    @field_validator("course_styles", "other_preferences")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _deduplicate_text(value)


class RecommendationConstraints(_StrictInputModel):
    target_term: ShortText | None = None
    candidate_course_codes: list[ShortText] | None = Field(default=None, max_length=100)
    max_recommendations: int = Field(default=8, ge=1, le=10)

    @field_validator("candidate_course_codes")
    @classmethod
    def normalize_candidate_codes(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalize_candidate_codes(value)


class RoleProfileInput(_StrictInputModel):
    """Role evidence already resolved by the upstream agent."""

    role_id: ShortText
    role_title: LongText
    required_skills: list[SkillId] = Field(min_length=1, max_length=9)

    @field_validator("required_skills")
    @classmethod
    def deduplicate_skills(cls, value: list[SkillId]) -> list[SkillId]:
        return _deduplicate_skills(value)


class CourseCatalogItemInput(_StrictInputModel):
    """One complete course record supplied by the upstream agent."""

    code: ShortText
    title: LongText
    units: int = Field(ge=0, le=40)
    section: LongText = ""
    skills: list[SkillId] = Field(default_factory=list, max_length=9)
    description: str = Field(default="", max_length=5000)
    prerequisite_text: str = Field(default="", max_length=3000)
    preclusion_text: str = Field(default="", max_length=3000)
    can_recommend: bool
    # Optional verified display data from the upstream agent. These fields
    # must never be inferred from semester_count or fetched by this domain.
    offered_terms: list[ShortText] = Field(default_factory=list, max_length=20)
    course_time: LongText | None = None
    source_url: str = Field(default="", max_length=2048)

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

    schema_version: SchemaVersion = "2.0"
    request_id: str = Field(
        default_factory=lambda: uuid4().hex, min_length=1, max_length=100
    )
    # Correlation metadata only. The recommendation domain must never use it
    # to retrieve profile or course data.
    user_id: str | None = Field(default=None, min_length=1, max_length=100)
    goals: GoalInput = Field(default_factory=GoalInput)
    background: BackgroundInput = Field(default_factory=BackgroundInput)
    preferences: PreferenceInput = Field(default_factory=PreferenceInput)
    constraints: RecommendationConstraints = Field(
        default_factory=RecommendationConstraints
    )
    role_profile: RoleProfileInput | None = None
    course_catalog: list[CourseCatalogItemInput] = Field(min_length=1, max_length=500)
    curriculum_rules: list[CurriculumRuleInput] = Field(min_length=1, max_length=100)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list, max_length=100)
    field_sources: dict[FieldPath, InputSource] = Field(
        default_factory=dict, max_length=50
    )

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
