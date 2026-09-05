"""
Password hashing and JWT issuance/verification — pure functions, no
database access (see repository.py for that) and no HTTP concerns (see
service.py for how these are wired into register/login/
get_current_user_id).

Uses bcrypt directly rather than passlib — passlib has known compatibility
issues with recent bcrypt releases, and no other domain in this project
uses it, so there's no existing convention to match.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised for any invalid, expired, or malformed access token."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_verification_code() -> str:
    """A 6-digit numeric code, zero-padded — secrets.randbelow(), not the
    `random` module, since this needs to be unguessable, not just
    unpredictable-looking."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    """SHA-256, not bcrypt: a verification code's brute-force resistance
    comes from its short TTL and capped attempt count (see
    domains/auth/service.py), not from a deliberately slow hash — bcrypt's
    cost factor would just add latency to every check for no benefit here.
    Passwords (hash_password above) are the opposite case: no TTL/attempt
    cap bounds a password's exposure, so the slow hash is what's doing the
    work there."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    return hashlib.sha256(code.encode("utf-8")).hexdigest() == code_hash


def create_access_token(user_id: str, email: str, role: str) -> tuple[str, int, str]:
    """Returns (token, expires_in_seconds, jti) — callers that need the jti
    (e.g. to blacklist it on logout) get it back without decoding the token
    they just made."""
    now = datetime.now(timezone.utc)
    expires_in = settings.jwt_access_token_expire_minutes * 60
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    return token, expires_in, jti


def decode_access_token(token: str) -> dict:
    """Returns the decoded payload, or raises TokenError for any invalid,
    expired, or malformed token."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
