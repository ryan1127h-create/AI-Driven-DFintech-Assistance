"""
Auth service — registration, login, logout, and the `get_current_user_id`
FastAPI dependency every other domain's api.py depends on (via
interface.py) to resolve who's calling.

This is the only domain that touches passwords/tokens directly — see
security.py for the hashing/JWT primitives and repository.py for the
student.users access underneath.
"""

from __future__ import annotations

import time

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.redis_cache_adapter import cache
from app.core.errors import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.domains.auth import repository
from app.domains.auth.schemas import TokenResponse, UserOut
from app.domains.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

logger = get_logger(__name__)

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
        raise ConflictError("An account with this email already exists.")

    row = repository.create(email, hash_password(password), full_name)
    token, expires_in, _jti = create_access_token(str(row["user_id"]), row["email"])
    return user_out(row), TokenResponse(access_token=token, expires_in=expires_in)


def login(email: str, password: str) -> tuple[UserOut, TokenResponse]:
    row = repository.get_by_email(email)
    # Same error for "no such user" and "wrong password" — avoids leaking
    # which emails are registered.
    if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        raise UnauthorizedError("Incorrect email or password.")

    repository.update_last_login(str(row["user_id"]))
    token, expires_in, _jti = create_access_token(str(row["user_id"]), row["email"])
    return user_out(row), TokenResponse(access_token=token, expires_in=expires_in)


def logout(token: str) -> None:
    """Blacklists this token's jti for its remaining lifetime, so
    get_current_user_id() starts rejecting it immediately instead of
    waiting out the full expiry. An already-invalid token has nothing to
    blacklist — treated as a no-op, since "logging out" a token that's
    already unusable isn't meaningfully different from success."""
    try:
        payload = decode_access_token(token)
    except TokenError:
        return

    ttl = payload["exp"] - int(time.time())
    if ttl <= 0:
        return
    try:
        cache.set(f"{_BLACKLIST_PREFIX}{payload['jti']}", "1", ttl_seconds=int(ttl))
    except Exception as exc:
        logger.warning("logout failed to write blacklist entry: %s", exc)


def _is_blacklisted(jti: str) -> bool:
    """Fail-open: a cache error is treated as "not blacklisted" rather than
    rejecting every authenticated request — the JWT's own expiry is the
    primary security boundary, the blacklist only accelerates logout."""
    try:
        return cache.exists(f"{_BLACKLIST_PREFIX}{jti}")
    except Exception as exc:
        logger.warning("blacklist check failed, allowing request: %s", exc)
        return False


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — every other domain's protected endpoints use
    this via interface.py to resolve the calling user_id."""
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise UnauthorizedError("Invalid or expired access token.")

    if _is_blacklisted(payload.get("jti", "")):
        raise UnauthorizedError("This access token has been logged out.")

    return payload["sub"]
