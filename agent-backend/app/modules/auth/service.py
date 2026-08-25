"""
Auth service — registration, login, logout, and the `get_current_user_id`
FastAPI dependency every other module's api.py imports (via
app/modules/auth/interface.py) to find out who's calling.

This is the ONLY module in the project that touches passwords/tokens —
see app/modules/auth/security.py for the actual hashing/JWT primitives and
app/modules/auth/repository.py for the student.users access underneath.
"""

from __future__ import annotations

import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.clients.redis_client import get_redis_client
from app.modules.auth import repository
from app.modules.auth.schemas import TokenResponse, UserOut
from app.modules.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

_bearer_scheme = HTTPBearer(auto_error=True)
_BLACKLIST_PREFIX = "auth:blacklist:"


def user_out(row: dict) -> UserOut:
    return UserOut(
        user_id=str(row["user_id"]),
        email=row["email"],
        full_name=row["full_name"],
        account_status=row.get("account_status"),
    )


def register(email: str, password: str, full_name: str) -> tuple[UserOut, TokenResponse]:
    if repository.get_by_email(email) is not None:
        raise ValueError("An account with this email already exists.")

    row = repository.create(email, hash_password(password), full_name)
    token, expires_in, _jti = create_access_token(str(row["user_id"]), row["email"])
    return user_out(row), TokenResponse(access_token=token, expires_in=expires_in)


def login(email: str, password: str) -> tuple[UserOut, TokenResponse]:
    row = repository.get_by_email(email)
    # Same error for "no such user" and "wrong password" — avoids leaking
    # which emails are registered.
    if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        raise PermissionError("Incorrect email or password.")

    repository.update_last_login(str(row["user_id"]))
    token, expires_in, _jti = create_access_token(str(row["user_id"]), row["email"])
    return user_out(row), TokenResponse(access_token=token, expires_in=expires_in)


def logout(token: str) -> None:
    """Blacklists this token's jti in Redis for its remaining lifetime, so
    get_current_user_id() starts rejecting it immediately instead of waiting
    out the full expiry. Invalid tokens have nothing to blacklist — treated
    as a no-op rather than an error, since "logging out" an already-invalid
    token isn't meaningfully different from success."""
    try:
        payload = decode_access_token(token)
    except TokenError:
        return

    ttl = payload["exp"] - int(time.time())
    if ttl <= 0:
        return
    try:
        get_redis_client().set(f"{_BLACKLIST_PREFIX}{payload['jti']}", "1", ex=int(ttl))
    except Exception as exc:
        print(f"[auth.service] Warning: logout failed to write blacklist entry — {exc}")


def _is_blacklisted(jti: str) -> bool:
    """Fail-open: a Redis error is treated as "not blacklisted" rather than
    rejecting every authenticated request — the JWT's own expiry is the
    primary security boundary, the blacklist only accelerates logout."""
    try:
        return get_redis_client().exists(f"{_BLACKLIST_PREFIX}{jti}") > 0
    except Exception as exc:
        print(f"[auth.service] Warning: blacklist check failed, allowing request — {exc}")
        return False


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — every other module's protected endpoints use
    this via app/modules/auth/interface.py to resolve the calling user_id."""
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")

    if _is_blacklisted(payload.get("jti", "")):
        raise HTTPException(status_code=401, detail="This access token has been logged out.")

    return payload["sub"]
