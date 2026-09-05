"""
Auth service — registration (with email verification), login, logout, and
the `get_current_user_id` FastAPI dependency every other domain's api.py
depends on (via interface.py) to resolve who's calling.

This is the only domain that touches passwords/tokens directly — see
security.py for the hashing/JWT primitives and repository.py for the
student.users access underneath.

Registration is two steps, never one: start_registration() validates the
request and emails a 6-digit code, but never writes to student.users — the
pending signup (password hash, full name, role, hashed code, attempt
count, and when the window opened) lives in Redis with a TTL instead.
verify_email() is the only place a row is ever created, so there's no such
thing as an abandoned unverified account sitting in the table needing
cleanup — a signup that's never verified just expires out of Redis on its
own.
"""

from __future__ import annotations

import json
import time

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.redis_cache_adapter import cache
from app.adapters.resend_email_adapter import email as email_sender
from app.core.config import settings
from app.core.errors import ConflictError, RateLimitError, ServiceUnavailableError, UnauthorizedError, ValidationError
from app.core.logging import get_logger
from app.domains.auth import repository
from app.domains.auth.schemas import AuthResponse, RegistrationStartedResponse, UserOut
from app.domains.auth.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_verification_code,
    hash_code,
    hash_password,
    verify_code,
    verify_password,
)

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)
_BLACKLIST_PREFIX = "auth:blacklist:"
_PENDING_PREFIX = "auth:pending:"
_ENROLLED_STUDENT_EMAIL_SUFFIX = "@u.nus.edu"


def user_out(row: dict) -> UserOut:
    return UserOut(
        user_id=str(row["user_id"]),
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        account_status=row.get("account_status"),
    )


def _auth_response(row: dict) -> AuthResponse:
    token, expires_in, _jti = create_access_token(str(row["user_id"]), row["email"], row["role"])
    return AuthResponse(access_token=token, expires_in=expires_in, user=user_out(row))


def _validate_email_for_role(email: str, role: str) -> None:
    """Enrolled-student accounts must prove NUS student email ownership via
    the domain itself; applicants can use any email since they don't yet
    have an NUS identity to check against."""
    if role == "enrolled_student" and not email.endswith(_ENROLLED_STUDENT_EMAIL_SUFFIX):
        raise ValidationError(
            f"Enrolled student accounts require a {_ENROLLED_STUDENT_EMAIL_SUFFIX} email address."
        )


def _verification_email_text(code: str) -> str:
    minutes = settings.email_verification_ttl_seconds // 60
    return (
        f"Your NUS DFT verification code is {code}.\n\n"
        f"This code expires in {minutes} minutes. If you didn't request this, "
        f"you can safely ignore this email — no account will be created without it."
    )


def _pending_key(email: str) -> str:
    return f"{_PENDING_PREFIX}{email}"


def _load_pending(email: str) -> dict | None:
    raw = cache.get(_pending_key(email))
    return json.loads(raw) if raw is not None else None


def _save_pending(email: str, pending: dict, ttl_seconds: int) -> None:
    cache.set(_pending_key(email), json.dumps(pending), ttl_seconds=ttl_seconds)


def _send_code(email: str, full_name: str, password_hash: str, role: str) -> RegistrationStartedResponse:
    """Issues a brand-new code and a brand-new full verification window —
    used both for a first registration attempt and for an explicit resend.
    Contrast with verify_email()'s wrong-code path, which re-saves the
    *same* pending entry without resetting created_at/the window, so
    repeated wrong guesses can't be used to keep a signup alive
    indefinitely (see settings.email_verification_max_attempts for the
    actual bound on guesses)."""
    code = generate_verification_code()
    # Send before persisting: if delivery fails, this must not leave behind
    # a pending entry that looks "successfully sent" — that would falsely
    # trip the resend cooldown on the caller's very next, legitimate retry.
    try:
        email_sender.send(email, "Your NUS DFT verification code", _verification_email_text(code))
    except Exception as exc:
        logger.error("failed to send verification email to %s: %s", email, exc)
        raise ServiceUnavailableError(
            "We couldn't send the verification email right now. Please try again in a few minutes."
        ) from exc
    now = time.time()
    _save_pending(
        email,
        {
            "password_hash": password_hash, "full_name": full_name, "role": role,
            "code_hash": hash_code(code), "attempts": 0, "created_at": now, "last_sent_at": now,
        },
        ttl_seconds=settings.email_verification_ttl_seconds,
    )
    return RegistrationStartedResponse(email=email, expires_in=settings.email_verification_ttl_seconds)


def _check_resend_cooldown(pending: dict) -> None:
    elapsed = time.time() - pending.get("last_sent_at", 0)
    if elapsed < settings.email_verification_resend_cooldown_seconds:
        wait = int(settings.email_verification_resend_cooldown_seconds - elapsed)
        raise RateLimitError(f"A verification code was already sent; please wait {wait}s before trying again.")


def start_registration(email: str, password: str, full_name: str, role: str) -> RegistrationStartedResponse:
    email = email.strip().lower()
    _validate_email_for_role(email, role)

    if repository.get_by_email(email) is not None:
        raise ConflictError("An account with this email already exists.")

    pending = _load_pending(email)
    if pending is not None:
        _check_resend_cooldown(pending)

    return _send_code(email, full_name, hash_password(password), role)


def resend_code(email: str) -> RegistrationStartedResponse:
    """Always returns the same shape whether or not `email` actually has a
    pending registration — telling the caller "no pending signup found"
    would let someone probe which emails have started registering."""
    email = email.strip().lower()
    pending = _load_pending(email)
    if pending is None:
        return RegistrationStartedResponse(email=email, expires_in=settings.email_verification_ttl_seconds)

    _check_resend_cooldown(pending)
    return _send_code(email, pending["full_name"], pending["password_hash"], pending["role"])


def verify_email(email: str, code: str) -> AuthResponse:
    email = email.strip().lower()
    pending = _load_pending(email)
    if pending is None:
        raise ValidationError("This verification code has expired or was never issued. Please register again.")

    if pending["attempts"] >= settings.email_verification_max_attempts:
        cache.delete(_pending_key(email))
        raise RateLimitError("Too many incorrect attempts. Please register again.")

    if not verify_code(code, pending["code_hash"]):
        remaining = settings.email_verification_ttl_seconds - (time.time() - pending["created_at"])
        if remaining <= 0:
            cache.delete(_pending_key(email))
            raise ValidationError("This verification code has expired. Please register again.")
        pending["attempts"] += 1
        _save_pending(email, pending, ttl_seconds=int(remaining))  # same window, doesn't get extended
        raise ValidationError("Incorrect verification code.")

    row = repository.create(email, pending["password_hash"], pending["full_name"], pending["role"])
    cache.delete(_pending_key(email))
    return _auth_response(row)


def login(email: str, password: str, role: str) -> AuthResponse:
    row = repository.get_by_email(email.strip().lower())
    # Same error for "no such user" and "wrong password" — avoids leaking
    # which emails are registered.
    if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        raise UnauthorizedError("Incorrect email or password.")

    # Checked only after the password has already matched, so this can
    # never be used to probe which emails exist — the caller already had
    # to prove they know the password before this check runs at all. Catches
    # the "picked the wrong portal/tab" mistake with a clearer message than
    # a generic auth failure (e.g. an applicant trying the Enrolled Student
    # tab, or anyone trying the Staff/Admin tab on a non-admin account).
    if row["role"] != role:
        raise UnauthorizedError(f"This account is not registered as {role.replace('_', ' ')}.")

    repository.update_last_login(str(row["user_id"]))
    return _auth_response(row)


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
