"""HTTP models for the lifecycle domain (see api.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProgrammeOut(BaseModel):
    code: str
    name: Optional[str] = None
    total_units_required: Optional[int] = None


class AcademicRecordOut(BaseModel):
    study_mode: Optional[str] = None
    track: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    academic_standing: Optional[str] = None
    gpa_band: Optional[str] = None
    expected_grad_term: Optional[str] = None
    graduation_term: Optional[str] = None


class EnrolledCourseOut(BaseModel):
    """One course enrollment: completed, current or planned."""

    course_code: str
    title: Optional[str] = None
    term: Optional[str] = None
    status: str
    grade_band: Optional[str] = None
    units: Optional[float] = None
    requirement_role: str


class DegreeProgressOut(BaseModel):
    """See course_recommendation's models.DegreeProgress."""

    core_mandatory_done: list[str]
    core_mandatory_remaining: list[str]
    core_choice_done: list[str]
    core_choice_remaining_count: int
    core_choice_surplus: list[str]
    core_replacement_cautions: list[str]
    capstone_path: str
    elective_units_done: int
    elective_units_target: int
    elective_level4000_used: int
    elective_level4000_cap_reached: bool
    total_units_done: int
    total_units_target: int


class LifecycleResponse(BaseModel):
    user_id: str
    lifecycle_stage: str
    programme: ProgrammeOut
    record: Optional[AcademicRecordOut] = None
    courses: list[EnrolledCourseOut] = Field(default_factory=list)
    # From completed courses only, and with the current ones counted as if
    # already passed.
    progress: DegreeProgressOut
    projected_progress: DegreeProgressOut
