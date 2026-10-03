"""HTTP request/response models for the profile domain (see api.py).

Field values are JSON of whatever shape the field's definition says
(GET /profile/definitions); they are validated against the field
dictionary in service.py, not here."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileField(BaseModel):
    value: Any
    source: str
    verified: bool
    updated_at: Optional[datetime] = None
    editable: bool
    locked_reason: Optional[str] = None
    # For a value stored from a CV: the CV line it came from.
    cv_quote: Optional[str] = None


class ProfileOut(BaseModel):
    user_id: str
    fields: dict[str, ProfileField]
    open_conflicts: int = 0


class FieldDefinition(BaseModel):
    field_key: str
    module: str
    label: str
    value_type: str
    allowed_values: Optional[list] = None
    value_labels: Optional[dict] = None
    values_ref: Optional[str] = None
    max_items: Optional[int] = None
    tier: str
    stages: list[str]
    sources: list[str]
    value_spec: Optional[str] = None
    description: Optional[str] = None
    editable: bool
    locked_reason: Optional[str] = None


class DefinitionsOut(BaseModel):
    fields: list[FieldDefinition]
    role_tags: dict[str, Optional[str]]


class ProfileUpdate(BaseModel):
    """{field_key: value}; null deletes the field. At most 60 fields at once."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Any] = Field(max_length=60)
    # Set when the answers were reviewed after a CV import; values equal to
    # that import's candidates are then stored as source CV.
    cv_document_id: Optional[UUID] = None


class ConflictOut(BaseModel):
    id: int
    field_key: str
    label: Optional[str] = None
    kind: str
    current_value: Any = None
    current_source: Optional[str] = None
    candidate_value: Any
    candidate_source: str
    created_at: datetime


class ConflictResolution(BaseModel):
    action: Literal["accept_candidate", "keep_current", "dismiss"]


class ConsentOut(BaseModel):
    key: str
    label: Optional[str] = None
    description: Optional[str] = None
    granted: bool
    updated_at: Optional[datetime] = None


class ConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consents: dict[str, bool]
