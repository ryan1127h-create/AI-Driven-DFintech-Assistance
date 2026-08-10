"""HTTP request/response models for the profile module (see
app/modules/profile/api.py)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

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


class ProfilePatch(BaseModel):
    """Fields a user can confirm or correct after resume extraction."""

    model_config = ConfigDict(extra="forbid")

    lifecycle_stage: Optional[LifecycleStage] = None
    academic_background_raw: Optional[str] = None
    academic_background_std: Optional[str] = Field(default=None, max_length=100)
    tech_level_raw: Optional[str] = None
    tech_level_std: Optional[TechLevel] = None
    school_tier: Optional[str] = Field(default=None, max_length=50)
    work_years: Optional[int] = Field(default=None, ge=0, le=80)
    gmat: Optional[int] = Field(default=None, ge=200, le=800)
    gre: Optional[int] = Field(default=None, ge=260, le=340)
    toefl: Optional[int] = Field(default=None, ge=0, le=120)
    ielts: Optional[float] = Field(default=None, ge=0, le=9)
    target_role_raw: Optional[str] = None
    target_role_std: Optional[TargetRole] = None
    target_industry_raw: Optional[str] = None
    target_industry_std: Optional[str] = Field(default=None, max_length=100)
    application_term: Optional[str] = Field(default=None, max_length=50)
    intake_year: Optional[int] = Field(default=None, ge=2000, le=2100)
