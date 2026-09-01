"""Request/response schemas for the career_planning API — kept separate
from the internal domain models."""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field

# Free text on purpose: standard role ids get curated skill data, any other
# role is mapped to our skill tags by AI (stated in the response `notes`).
TargetRoleText = Annotated[str, Field(max_length=100)]
ShortText = Annotated[str, Field(max_length=100)]


class CareerPlanRequest(BaseModel):
    # All optional: no target_role -> the stored profile's role. timeline
    # and region only steer the wording of the plan.
    target_role: Optional[TargetRoleText] = None
    timeline: Optional[ShortText] = None
    region: Optional[ShortText] = None


class PlannedCourse(BaseModel):
    course_code: str
    course_title: str
    priority: str
    reason: str


class CareerPlanResponse(BaseModel):
    target_role: Optional[str]
    current_fit: str
    skill_gaps: list[str]
    recommended_courses: list[PlannedCourse]
    short_term_actions: list[str]
    medium_term_actions: list[str]
    notes: list[str]
    sources: list[str]
