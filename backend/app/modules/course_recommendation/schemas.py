"""Request/response schemas for the course_recommendation API — kept
separate from the internal domain models (models.py), mirroring the
profile module's schemas.py/models.py split."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

# Per-item bounds: course codes are short (e.g. "FT5005"), and preference
# keywords are substring-matched against every course description, so
# unbounded strings would be both meaningless and wastefully scanned.
CourseCode = Annotated[str, Field(max_length=20)]
PreferenceKeyword = Annotated[str, Field(max_length=100)]

# Free text on purpose: the 6 standard role ids get curated skill data, any
# other role is mapped to our skill tags by AI (stated in the response
# `notes`). See service.py::_resolve_role_skills.
TargetRoleText = Annotated[str, Field(max_length=100)]


class CourseRecommendationRequest(BaseModel):
    # All optional: with nothing supplied the target role falls back to the
    # stored profile's target_role_std, and with no signal at all the
    # response is the remaining Core Courses (stated as such in `notes`).
    target_role: Optional[TargetRoleText] = None
    completed_courses: list[CourseCode] = Field(default_factory=list, max_length=40)
    preferences: list[PreferenceKeyword] = Field(default_factory=list, max_length=10)


class RecommendedCourse(BaseModel):
    course_code: str
    course_title: str
    units: int
    section: str
    priority: Literal["high", "medium", "low"]
    matched_skills: list[str]
    reason: str


class CourseRecommendationResponse(BaseModel):
    target_role: Optional[str]
    recommended_courses: list[RecommendedCourse]
    skill_gaps: list[str]
    completed_recognized: list[str]
    completed_unrecognized: list[str]
    completed_units: int
    notes: list[str]
    sources: list[str]
