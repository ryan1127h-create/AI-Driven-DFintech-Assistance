from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alumni_id: str
    note: str | None = Field(default=None, max_length=300)


class RequestUpdate(BaseModel):
    """An alumnus accepts (sharing the chosen contact details) or declines;
    a student cancels their own pending request."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "decline", "cancel"]
    share: list[Literal["email", "phone", "linkedin"]] = []
    reply_note: str | None = Field(default=None, max_length=300)


class ListedUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listed: bool


class StaffAlumnusFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    class_year: int | None = Field(default=None, ge=1990, le=2100)
    expertise: list[str] | None = None
    bio: str | None = Field(default=None, max_length=2000)
    photo_url: str | None = Field(default=None, max_length=1000)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)
    linkedin_url: str | None = Field(default=None, max_length=500)
    listed: bool | None = None


class StaffAlumnusCreate(StaffAlumnusFields):
    email: str = Field(max_length=320)
