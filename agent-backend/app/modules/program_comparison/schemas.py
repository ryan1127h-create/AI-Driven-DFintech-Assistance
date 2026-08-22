"""Request/response schemas for the program_comparison API — kept separate
from the internal domain models (models.py), mirroring the other modules."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

ProgramName = Annotated[str, Field(max_length=100)]
TargetRoleText = Annotated[str, Field(max_length=100)]

# "career" is accepted but currently answered with a "no data" note.
ComparisonFocus = Literal["curriculum", "fees", "admission", "career"]


class ProgramComparisonRequest(BaseModel):
    # All optional: no programs -> NUS + all competitors; no focus -> all
    # data-backed dimensions; no target_role -> the stored profile's role.
    programs: list[ProgramName] = Field(default_factory=list, max_length=5)
    focus: list[ComparisonFocus] = Field(default_factory=list)
    target_role: Optional[TargetRoleText] = None


class ComparisonRow(BaseModel):
    dimension: str
    values: dict[str, str]  # programme name -> cell text


class MatchSubScore(BaseModel):
    name: str
    weight: float
    score: int
    included: bool  # False = data was missing, component left out of total
    evidence: str


class ProgramMatchScore(BaseModel):
    program: str
    total: Optional[int]  # None = not enough data for any component
    subscores: list[MatchSubScore]


class ComparisonOptionsResponse(BaseModel):
    programs: list[str]  # exact names, use as dropdown options
    dimensions: list[str]


class ProgramComparisonResponse(BaseModel):
    programs: list[str]
    comparison_table: list[ComparisonRow]
    match_scores: list[ProgramMatchScore]
    program_comments: dict[str, str]
    best_fit_summary: str
    notes: list[str]
    sources: list[str]
