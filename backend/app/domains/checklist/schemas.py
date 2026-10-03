"""HTTP models for the checklist domain (see api.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApplicationDocument(BaseModel):
    """One admissions document and whether the school has received it."""

    item_key: str
    label: Optional[str] = None
    description: Optional[str] = None
    required: bool = False
    submitted: bool


class ApplicationOut(BaseModel):
    """The user's bound admission application, as the school records it."""

    application_no: Optional[str] = None
    application_type: Optional[str] = None
    admission_term: Optional[str] = None
    submission_date: Optional[datetime] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    next_step: Optional[str] = None
    documents: list[ApplicationDocument] = Field(default_factory=list)


class ChecklistResponse(BaseModel):
    user_id: str
    lifecycle_stage: Optional[str] = None
    application: Optional[ApplicationOut] = None


class BindApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_no: str = Field(min_length=1, max_length=64)
