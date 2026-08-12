"""HTTP models for the checklist module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ChecklistCategory = Literal[
    "profile",
    "admission_document",
    "test_score",
    "reference",
    "finance",
    "other",
]
ChecklistRequirement = Literal["required", "conditional", "recommended", "optional"]
ChecklistStatus = Literal[
    "unknown",
    "not_started",
    "in_progress",
    "completed",
    "not_applicable",
]
ImplementationStatus = Literal["contract_only", "partial", "implemented"]


class ChecklistItem(BaseModel):
    id: str = Field(..., max_length=80)
    title: str = Field(..., max_length=160)
    category: ChecklistCategory
    requirement: ChecklistRequirement
    status: ChecklistStatus = "unknown"
    owner: str = Field(default="student", max_length=80)
    description: Optional[str] = None
    evidence_source: Optional[str] = Field(default=None, max_length=160)
    blocking_fields: list[str] = Field(default_factory=list)
    note: Optional[str] = None
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChecklistResponse(BaseModel):
    user_id: str
    lifecycle_stage: Optional[str] = None
    implementation_status: ImplementationStatus = "contract_only"
    items: list[ChecklistItem]
    outstanding_required_count: int = 0
    notes: list[str] = Field(default_factory=list)


class ChecklistItemPatch(BaseModel):
    """Persisted update for one checklist item."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[ChecklistStatus] = None
    evidence_source: Optional[str] = Field(default=None, max_length=160)
    note: Optional[str] = Field(default=None, max_length=500)
