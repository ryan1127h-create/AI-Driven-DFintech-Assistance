"""HTTP models for the cv_import domain (see api.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CvImportField(BaseModel):
    field_key: str
    label: Optional[str] = None
    value: Any
    display: str
    # The exact CV text the value comes from.
    quote: str
    # Compared with the profile now: "new" pre-fills the questionnaire,
    # "different" is a conflict for the user to settle on the profile page.
    status: Literal["new", "same", "different"]


class CvImportOut(BaseModel):
    document_id: str
    parse_status: str
    error: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    fields: list[CvImportField] = Field(default_factory=list)
