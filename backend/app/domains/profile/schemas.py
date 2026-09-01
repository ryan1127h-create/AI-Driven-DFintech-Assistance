"""HTTP request/response models for the profile domain (see api.py)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

LifecycleStage = Literal["prospect", "applicant", "admitted", "enrolled", "alumni"]
TechLevel = Literal["none", "basic", "strong"]
TargetRole = Literal[
    "quant_risk",
    "data_analytics",
    "fintech_pm",
    "payments",
    "digital_banking",
    "compliance_regtech",
]
AcademicBackground = Literal["finance", "cs_computing", "engineering", "business", "other"]


# ProfileOut deliberately does NOT use the Literal types above for its
# _std fields (plain Optional[str] instead) — this is the read side, and a
# stored value that predates a constraint being added must still be
# readable rather than fail to serialize. The Literal types are for the
# write side (ProfilePatch) only, where rejecting an invalid value with a
# 422 is exactly what should happen.
class ProfileOut(BaseModel):
    user_id: str
    lifecycle_stage: Optional[str] = None
    academic_background_raw: Optional[str] = None
    academic_background_std: Optional[str] = None
    tech_level_raw: Optional[str] = None
    tech_level_std: Optional[str] = None
    school_tier: Optional[str] = None
    work_years: Optional[int] = None
    gmat: Optional[int] = None
    gre: Optional[int] = None
    toefl: Optional[int] = None
    ielts: Optional[float] = None
    target_role_raw: Optional[str] = None
    target_role_std: Optional[str] = None
    target_industry_raw: Optional[str] = None
    target_industry_std: Optional[str] = None
    application_term: Optional[str] = None
    intake_year: Optional[int] = None
    completed_courses: Optional[list[str]] = None


class ProfilePatch(BaseModel):
    """Fields a user can confirm or correct after résumé extraction."""

    model_config = ConfigDict(extra="forbid")

    lifecycle_stage: Optional[LifecycleStage] = None
    # The four "_raw" fields below are free text (the applicant's/résumé's
    # own wording) rather than a constrained enum, so they need an explicit
    # length cap of their own — max_length=300 is generous for "a short
    # description close to their own wording" while still bounding how
    # much unvalidated free text can reach the database and, from there,
    # get re-injected into this user's own chatbot system prompt (see
    # interface.py::render_profile_summary).
    academic_background_raw: Optional[str] = Field(default=None, max_length=300)
    academic_background_std: Optional[AcademicBackground] = None
    tech_level_raw: Optional[str] = Field(default=None, max_length=300)
    tech_level_std: Optional[TechLevel] = None
    school_tier: Optional[str] = Field(default=None, max_length=50)
    work_years: Optional[int] = Field(default=None, ge=0, le=80)
    gmat: Optional[int] = Field(default=None, ge=200, le=800)
    gre: Optional[int] = Field(default=None, ge=260, le=340)
    toefl: Optional[int] = Field(default=None, ge=0, le=120)
    ielts: Optional[float] = Field(default=None, ge=0, le=9)
    target_role_raw: Optional[str] = Field(default=None, max_length=300)
    target_role_std: Optional[TargetRole] = None
    target_industry_raw: Optional[str] = Field(default=None, max_length=300)
    target_industry_std: Optional[str] = Field(default=None, max_length=100)
    application_term: Optional[str] = Field(default=None, max_length=50)
    intake_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    completed_courses: Optional[list[str]] = Field(default=None, max_length=50)

    @field_validator("completed_courses")
    @classmethod
    def clean_completed_courses(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            course = item.strip()
            if not course:
                continue
            if len(course) > 120:
                raise ValueError("Each completed course must be 120 characters or fewer.")
            key = course.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(course)
        return cleaned
