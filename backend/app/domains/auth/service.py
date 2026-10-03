"""
Auth service — registration (with email verification), login, logout, and
the `get_current_user_id` FastAPI dependency every other domain's api.py
depends on (via interface.py) to resolve who's calling.

This is the only domain that touches tokens/Supabase Auth directly — see
security.py for the verification-code/JWT-verification primitives,
app/adapters/supabase_auth_adapter.py for the actual account
creation/sign-in/sign-out calls, and repository.py for the account.accounts
access underneath (keyed by Supabase's own user id, not an independent
identity — the row is created by a trigger when the Supabase user is).

Roles: the database stores only 'user' | 'admin'. The app-level role the
frontend routes on — applicant / enrolled_student / admin — is derived
(derive_role): admin from the account, otherwise from the profile's
lifecycle_stage, which registration records from the role the user picked.
Admin accounts can log in but never register here.

Registration depends on the role picked:
  - applicant: any email, no verification — start_registration() creates
    the account (lifecycle 'prospect' until they bind an application on
    the checklist page) and logs it in straight away.
  - enrolled_student: an @u.nus.edu email that must be proved.
    start_registration() only emails a 6-digit code; the pending signup
    (password, full name, role, hashed code, attempt count, and when the
    window opened) lives in Redis with a TTL. verify_email() is the only
    place such an account is created, so there's no such thing as an
    abandoned unverified account sitting around needing cleanup — a signup
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
from app.core.errors import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domains.auth import repository
from app.domains.auth.schemas import AuthResponse, RegistrationStartedResponse, UserOut
from app.domains.profile import interface as profile_interface
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

# lifecycle_stage recorded for the role picked at registration (an
# applicant becomes 'applicant' only once they bind an application, see the
# checklist domain), and the stages that make a 'user' account an
# enrolled_student (everything else, including no stage on file, is an
# applicant).
_REGISTRATION_STAGE = {"applicant": "prospect", "enrolled_student": "current"}
_ENROLLED_STAGES = {"current", "graduating", "alumni"}


def derive_role(account_role: str, lifecycle_stage: str | None) -> str:
    if account_role == "admin":
        return "admin"
    return "enrolled_student" if lifecycle_stage in _ENROLLED_STAGES else "applicant"


def _lifecycle_stage(user_id: str) -> str | None:
    """Fail-soft: a profile read error degrades to "no stage on file"
    rather than blocking login."""
    try:
        return profile_interface.get_profile_field(user_id, "lifecycle_stage")
    except Exception as exc:
        logger.warning("could not read lifecycle_stage for %s: %s", user_id, exc)
        return None


def _onboarding_status(user_id: str) -> str | None:
    """Fail-soft like _lifecycle_stage(): unknown rather than a failed login."""
    try:
        return repository.get_onboarding_status(user_id)
    except Exception as exc:
        logger.warning("could not read onboarding_status for %s: %s", user_id, exc)
        return None


def user_out(account: dict, lifecycle_stage: str | None) -> UserOut:
    return UserOut(
        user_id=str(account["user_id"]),
        email=account["email"],
        full_name=account["full_name"] or "",
        role=derive_role(account["role"], lifecycle_stage),
        account_status=account.get("account_status"),
        lifecycle_stage=lifecycle_stage,
        onboarding_status=_onboarding_status(str(account["user_id"])),
    )


def get_user(user_id: str) -> UserOut | None:
    account = repository.get_account(user_id)
    if account is None:
        return None
    return user_out(account, _lifecycle_stage(user_id))


def update_full_name(user_id: str, full_name: str) -> UserOut:
    """The account row is what the app reads; Supabase's user metadata is
    kept in step on a best-effort basis (it is only the copy the account
    row was created from)."""
    if not repository.set_full_name(user_id, full_name):
        raise NotFoundError("User not found.")
    try:
        auth_provider.update_full_name(user_id, full_name)
    except Exception as exc:
        logger.warning("could not update the Supabase name of %s: %s", user_id, exc)
    return get_user(user_id)


def get_settings(user_id: str) -> dict:
    settings_row = repository.get_settings(user_id)
    if settings_row is None:
        raise NotFoundError("User not found.")
    return settings_row


def update_settings(user_id: str, changes: dict) -> dict:
    settings_row = repository.update_settings(user_id, changes)
    if settings_row is None:
        raise NotFoundError("User not found.")
    return settings_row


def set_onboarding_status(user_id: str, status: str) -> UserOut:
    if not repository.set_onboarding_status(user_id, status):
        raise NotFoundError("User not found.")
    return get_user(user_id)


def _auth_response(session: AuthSession, user: UserOut) -> AuthResponse:
    return AuthResponse(access_token=session.access_token, expires_in=session.expires_in, user=user)


def _create_account(
    email: str, password: str, full_name: str, role: str, consent_personalized_rec: bool
) -> AuthResponse:
    """Creates the Supabase user (which creates the account/settings/
    profile rows via trigger), records the registration role as the
    profile's lifecycle_stage and the personalization consent decision,
    and logs the new account in."""
    user_id = auth_provider.create_user(email, password, full_name)
    stage = _REGISTRATION_STAGE[role]
    try:
        profile_interface.set_lifecycle_stage(user_id, stage, source="QA", actor=f"user:{user_id}")
    except Exception as exc:
        # The account itself exists and is usable; without a stage it is
        # treated as an applicant until the profile records one.
        logger.warning("could not record lifecycle_stage for new user %s: %s", user_id, exc)
        stage = None
    try:
        profile_interface.record_consents(user_id, {"consent_personalized_rec": consent_personalized_rec})
    except Exception as exc:
        # Unrecorded means not granted; the user can still grant it later.
        logger.warning("could not record registration consent for new user %s: %s", user_id, exc)

    account = repository.get_account(user_id)
    if account is None:
        logger.error("account row missing right after creating auth user %s", user_id)
        raise ServiceUnavailableError("Your account was created but couldn't be loaded. Please try logging in.")
    # A fresh account has no session yet — admin.create_user() is a
    # sessionless admin operation, so signing in with the same credentials
    # right after is how this call ends up logged in immediately.
    session = auth_provider.sign_in(email, password)
    return _auth_response(session, user_out(account, stage))


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


def _send_code(
    email: str, full_name: str, password: str, role: str, consent_personalized_rec: bool
) -> RegistrationStartedResponse:
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
            "consent_personalized_rec": consent_personalized_rec,
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


def start_registration(
    email: str, password: str, full_name: str, role: str, consent_personalized_rec: bool = False
) -> AuthResponse | RegistrationStartedResponse:
    """An applicant is registered and logged in immediately (AuthResponse);
    an enrolled student is emailed a code to confirm via verify_email()
    (RegistrationStartedResponse)."""
    email = email.strip().lower()
    _validate_email_for_role(email, role)

    if repository.get_account_by_email(email) is not None:
        raise ConflictError("An account with this email already exists.")

    if role == "applicant":
        return _create_account(email, password, full_name, role, consent_personalized_rec)

    pending = _load_pending(email)
    if pending is not None:
        _check_resend_cooldown(pending)

    return _send_code(email, full_name, password, role, consent_personalized_rec)


def resend_code(email: str) -> RegistrationStartedResponse:
    """Always returns the same shape whether or not `email` actually has a
    pending registration — telling the caller "no pending signup found"
    would let someone probe which emails have started registering."""
    email = email.strip().lower()
    pending = _load_pending(email)
    if pending is None:
        return RegistrationStartedResponse(email=email, expires_in=settings.email_verification_ttl_seconds)

    _check_resend_cooldown(pending)
    return _send_code(
        email, pending["full_name"], pending["password"], pending["role"],
        pending.get("consent_personalized_rec", False),
    )


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

    # Pre-confirmed (email_confirm=True): our own code above already proved
    # ownership, so Supabase never needs to send its own confirmation email.
    response = _create_account(
        email, pending["password"], pending["full_name"], pending["role"],
        pending.get("consent_personalized_rec", False),
    )
    cache.delete(_pending_key(email))
    return response


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

    account = repository.get_account(session.user_id)
    if account is None:
        # Supabase has an account but this app's own account row is
        # missing — shouldn't happen in normal operation, but treated the
        # same as "no such user" rather than surfacing an internal-looking
        # error to an authenticated-with-Supabase-but-unknown-to-us caller.
        raise UnauthorizedError("Incorrect email or password.")

    # Both checks below run only after the password has already matched,
    # so they can never be used to probe which emails exist.
    if account["account_status"] != "active":
        raise UnauthorizedError("This account has been disabled.")

    # Catches the "picked the wrong portal/tab" mistake with a clearer
    # message than a generic auth failure (e.g. an applicant trying the
    # Enrolled Student tab, or anyone trying the Staff/Admin tab on a
    # non-admin account).
    user = user_out(account, _lifecycle_stage(session.user_id))
    if user.role != role:
        raise UnauthorizedError(f"This account is not registered as {role.replace('_', ' ')}.")

    repository.touch_last_login(user.user_id)
    return _auth_response(session, user)


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
