"""Domain model for a user profile row — mirrors the sandbox
`student.user_profiles` table columns (see
app/modules/profile/schema/student_schema_clone.sql)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserProfile:
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
