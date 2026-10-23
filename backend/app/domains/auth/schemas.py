"""HTTP request/response models for the auth domain (see api.py)."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Self-registerable roles only — "admin" is deliberately excluded (see
# service.py::start_registration): staff/admin accounts are provisioned
# directly in the database, not through this endpoint. A prior version of
# this project had an unauthenticated staff-registration endpoint; closing
# self-service admin signup here is a deliberate choice, not an oversight.
SelfRegisterableRole = Literal["applicant", "enrolled_student"]

# The app-level role the frontend routes on. Not a stored column: the
# database only knows account.accounts.role ('user' | 'admin'); for a
# 'user' account, applicant vs enrolled_student is derived from the
# profile's lifecycle_stage (see service.py::derive_role). Used at login,
# where the caller picks which portal they're entering through and that
# choice is validated against the account's derived role.
Role = Literal["applicant", "enrolled_student", "admin"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=255)
    role: SelfRegisterableRole
    # "Use my profile to personalize recommendations" — recorded as the
    # consent_personalized_rec decision when the account is created.
    consent_personalized_rec: bool = False


class RegistrationStartedResponse(BaseModel):
    status: Literal["verification_sent"] = "verification_sent"
    email: str
    expires_in: int  # seconds


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    role: Role


class UserOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str  # derived app role, see Role above
    account_status: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    # The stage the assistant serves the user as (app/core/stage_policy.py):
    # the lifecycle stage, or "rejected" for an applicant whose latest
    # application was rejected. The client picks suggested prompts by it.
    policy_stage: Optional[str] = None
    # not_started / skipped / completed, see repository.ONBOARDING_STATUSES.
    onboarding_status: Optional[str] = None


class OnboardingUpdate(BaseModel):
    """The welcome questionnaire was skipped or finished; it can't be reset
    to not_started (the profile page and the chat reminder reopen it)."""

    status: Literal["skipped", "completed"]


class AuthResponse(BaseModel):
    """Returned by whichever endpoint actually logs the caller in
    (login, verify-email, and register for an applicant) — token and user
    together, so the frontend never has to make a second round trip (or
    decode the JWT client-side) just to learn the user's own role."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class SettingsOut(BaseModel):
    language_pref: list[str] = Field(default_factory=list)
    answer_depth: str = "standard"
    email_notifications: bool = False


class SettingsUpdate(BaseModel):
    """Only the settings given change. language_pref: up to 5 two-letter
    ISO 639-1 codes, in order of preference."""

    model_config = ConfigDict(extra="forbid")

    language_pref: Optional[list[str]] = Field(default=None, max_length=5)
    answer_depth: Optional[Literal["concise", "standard", "detailed"]] = None
    email_notifications: Optional[bool] = None

    @field_validator("language_pref")
    @classmethod
    def _codes(cls, value):
        if value is None:
            return value
        codes = [v.strip().lower() for v in value]
        if any(not re.fullmatch(r"[a-z]{2}", c) for c in codes):
            raise ValueError("language_pref takes two-letter language codes such as 'en' or 'zh'")
        return list(dict.fromkeys(codes))


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("full_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("full_name can't be blank")
        return value
