"""HTTP request/response models for the profile module (see
app/modules/profile/api.py)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


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
