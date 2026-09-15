"""HTTP request and response models for career planning."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


TargetRoleText = Annotated[str, Field(max_length=100)]
ShortText = Annotated[str, Field(max_length=100)]


class CareerPlanRequest(BaseModel):
    # The service falls back to the stored profile role when this is omitted.
    target_role: Optional[TargetRoleText] = None
    timeline: Optional[ShortText] = None
    region: Optional[ShortText] = None


class SkillAssessment(BaseModel):
    skill: str
    status: Literal["has", "partial", "missing", "unknown"]
    evidence: str


class CareerPhase(BaseModel):
    name: str
    timeframe: str
    actions: list[str]
    success_indicators: list[str]


class CareerPlanResponse(BaseModel):
    target_role: str
    current_fit: str
    skill_assessment: list[SkillAssessment]
    phases: list[CareerPhase]
    success_indicators: list[str]
    notes: list[str]
    sources: list[str]
