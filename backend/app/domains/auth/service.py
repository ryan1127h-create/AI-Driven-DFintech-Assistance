"""
Auth service — registration (with email verification), login, logout, and
the `get_current_user_id` FastAPI dependency every other domain's api.py
depends on (via interface.py) to resolve who's calling.

This is the only domain that touches tokens/Supabase Auth directly — see
security.py for the verification-code/JWT-verification primitives,
app/adapters/supabase_auth_adapter.py for the actual account
creation/sign-in/sign-out calls, and repository.py for the student.users
access underneath (an extension table keyed by Supabase's own user id, not
an independent identity).

Registration is two steps, never one: start_registration() validates the
request and emails a 6-digit code, but never creates an account — the
pending signup (password, full name, role, hashed code, attempt count, and
when the window opened) lives in Redis with a TTL instead. verify_email()
is the only place an account is ever created, so there's no such thing as
an abandoned unverified account sitting around needing cleanup — a signup
that's never verified just expires out of Redis on its own.
"""

from __future__ import annotations

import hashlib
import json
import time

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.redis_cache_adapter import cache
from app.adapters.resend_email_adapter import email as email_sender
from app.adapters.supabase_auth_adapter import auth_provider
from app.core.config import settings
from app.core.errors import ConflictError, RateLimitError, ServiceUnavailableError, UnauthorizedError, ValidationError
from app.core.logging import get_logger
from app.domains.auth import repository
from app.domains.auth.schemas import AuthResponse, RegistrationStartedResponse, UserOut
from app.domains.auth.security import (
    TokenError,
    decode_access_token,
    generate_verification_code,
    hash_code,
    verify_code,
)
from app.ports.auth_port import AuthenticationError, AuthSession

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


def _auth_response(session: AuthSession, row: dict) -> AuthResponse:
    return AuthResponse(access_token=session.access_token, expires_in=session.expires_in, user=user_out(row))


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


def _send_code(email: str, full_name: str, password: str, role: str) -> RegistrationStartedResponse:
    """Issues a brand-new code and a brand-new full verification window —
    used both for a first registration attempt and for an explicit resend.
    Contrast with verify_email()'s wrong-code path, which re-saves the
    *same* pending entry without resetting created_at/the window, so
    repeated wrong guesses can't be used to keep a signup alive
    indefinitely (see settings.email_verification_max_attempts for the
    actual bound on guesses).

    The pending entry holds the password in PLAIN TEXT (not a hash) —
    unlike the old self-managed bcrypt column, only Supabase Auth can hash
    it, and that only happens once verify_email() actually calls
    auth_provider.create_user(). This is a deliberate, bounded tradeoff:
    the plaintext only ever sits in Redis (already the trusted store behind
    the resend cooldown and logout blacklist) for at most
    settings.email_verification_ttl_seconds (default 10 minutes) before
    either being consumed and discarded, or expiring untouched."""
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
            "password": password, "full_name": full_name, "role": role,
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

    return _send_code(email, full_name, password, role)


def resend_code(email: str) -> RegistrationStartedResponse:
    """Always returns the same shape whether or not `email` actually has a
    pending registration — telling the caller "no pending signup found"
    would let someone probe which emails have started registering."""
    email = email.strip().lower()
    pending = _load_pending(email)
    if pending is None:
        return RegistrationStartedResponse(email=email, expires_in=settings.email_verification_ttl_seconds)

    _check_resend_cooldown(pending)
    return _send_code(email, pending["full_name"], pending["password"], pending["role"])


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

    password, full_name, role = pending["password"], pending["full_name"], pending["role"]
    # Pre-confirmed (email_confirm=True): our own code above already proved
    # ownership, so Supabase never needs to send its own confirmation email.
    user_id = auth_provider.create_user(email, password, full_name)
    row = repository.create(user_id, email, full_name, role)
    # A fresh account has no session yet — admin.create_user() is a
    # sessionless admin operation, so signing in with the same credentials
    # right after is how this call ends up logged in immediately, same as
    # before.
    session = auth_provider.sign_in(email, password)
    cache.delete(_pending_key(email))
    return _auth_response(session, row)


def login(email: str, password: str, role: str) -> AuthResponse:
    email = email.strip().lower()
    try:
        session = auth_provider.sign_in(email, password)
    except AuthenticationError:
        # Same error for "no such user" and "wrong password" — Supabase's
        # own sign-in endpoint already returns one generic error for both,
        # so this just carries that through without leaking which emails
        # are registered.
        raise UnauthorizedError("Incorrect email or password.")

    row = repository.get_by_id(session.user_id)
    if row is None:
        # Supabase has an account but this app's own extension row is
        # missing — shouldn't happen in normal operation, but treated the
        # same as "no such user" rather than surfacing an internal-looking
        # error to an authenticated-with-Supabase-but-unknown-to-us caller.
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
    return _auth_response(session, row)


def _token_fingerprint(token: str) -> str:
    """A fixed-length, non-reversible stand-in for the raw token as a Redis
    key — used instead of trusting a specific Supabase JWT claim name to
    double as a stable per-session identifier, since Supabase (not this
    app) controls that payload shape."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def logout(token: str) -> None:
    """Revokes the session with Supabase (so it can't be refreshed) and
    blacklists this exact access token for its remaining lifetime, so
    get_current_user_id() starts rejecting it immediately instead of
    waiting out the full expiry. An already-invalid token has nothing to
    revoke/blacklist — treated as a no-op, since "logging out" a token
    that's already unusable isn't meaningfully different from success."""
    try:
        payload = decode_access_token(token)
    except TokenError:
        return

    ttl = payload["exp"] - int(time.time())
    if ttl <= 0:
        return

    try:
        auth_provider.sign_out(token)
    except Exception as exc:
        logger.warning("logout failed to revoke the Supabase session: %s", exc)

    try:
        cache.set(f"{_BLACKLIST_PREFIX}{_token_fingerprint(token)}", "1", ttl_seconds=int(ttl))
    except Exception as exc:
        logger.warning("logout failed to write blacklist entry: %s", exc)


def _is_blacklisted(token: str) -> bool:
    """Fail-open: a cache error is treated as "not blacklisted" rather than
    rejecting every authenticated request — the JWT's own expiry is the
    primary security boundary, the blacklist only accelerates logout."""
    try:
        return cache.exists(f"{_BLACKLIST_PREFIX}{_token_fingerprint(token)}")
    except Exception as exc:
        logger.warning("blacklist check failed, allowing request: %s", exc)
        return False


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — every other domain's protected endpoints use
    this via interface.py to resolve the calling user_id."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except TokenError:
        raise UnauthorizedError("Invalid or expired access token.")

    if _is_blacklisted(token):
        raise UnauthorizedError("This access token has been logged out.")

    return payload["sub"]
