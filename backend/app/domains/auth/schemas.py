"""HTTP request/response models for the auth domain (see api.py)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

# Self-registerable roles only — "admin" is deliberately excluded (see
# service.py::start_registration): staff/admin accounts are provisioned
# directly in the database, not through this endpoint. A prior version of
# this project had an unauthenticated staff-registration endpoint; closing
# self-service admin signup here is a deliberate choice, not an oversight.
SelfRegisterableRole = Literal["applicant", "enrolled_student"]

# All three roles the DB CHECK constraint allows (see
# scripts/schema/0001_add_user_role.sql) — used at login, where the caller
# picks which portal they're entering through and that choice is validated
# against the account's actual stored role (see service.py::login).
Role = Literal["applicant", "enrolled_student", "admin"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=255)
    role: SelfRegisterableRole


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
    role: str
    account_status: Optional[str] = None


class AuthResponse(BaseModel):
    """Returned by whichever endpoint actually logs the caller in
    (login, verify-email) — token and user together, so the frontend never
    has to make a second round trip (or decode the JWT client-side) just to
    learn the user's own role."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut
