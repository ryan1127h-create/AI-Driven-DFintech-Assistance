"""
Verification-code helpers and access-token verification — pure functions,
no database access (see repository.py for that) and no HTTP concerns (see
service.py for how these are wired into register/login/
get_current_user_id).

Password hashing/checking and token issuance are NOT here — Supabase Auth
(auth.users) owns the account's password entirely (see
app/adapters/supabase_auth_adapter.py) and issues the access token itself;
this module only verifies a token Supabase already signed.
"""

from __future__ import annotations

import hashlib
import secrets

import jwt
from jwt import PyJWKClient

from app.core.config import settings

JWT_ALGORITHM = "ES256"
JWT_AUDIENCE = "authenticated"  # fixed value Supabase Auth stamps into every access token

# This project's Supabase Auth signs access tokens asymmetrically (ES256)
# with a key published at its own JWKS endpoint, rather than the legacy
# HS256-with-a-shared-secret setup older Supabase projects use — confirmed
# by decoding a real issued token's header (`alg: ES256`) against this
# endpoint. There is deliberately no "JWT secret" in config for this: the
# verification key is public by design (that's the point of asymmetric
# signing) and always fetched fresh from Supabase's own domain, so nothing
# here is a value that could be missing/weak/forged the way a shared secret
# could. PyJWKClient fetches and caches (default 300s) the key matching the
# token's own `kid` header, so verification stays local after first use.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


class TokenError(Exception):
    """Raised for any invalid, expired, or malformed access token."""


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
    A password is the opposite case: nothing bounds how long it might be
    exposed, which is why *that* needs a deliberately slow hash — which is
    exactly why Supabase Auth owns it instead of this app."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    return hashlib.sha256(code.encode("utf-8")).hexdigest() == code_hash


def decode_access_token(token: str) -> dict:
    """Returns the decoded payload of a Supabase Auth-issued access token,
    or raises TokenError for any invalid, expired, or malformed token, or
    one whose signature can't be verified against the current JWKS
    (including a lookup failure — e.g. no key matches the token's `kid`)."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=[JWT_ALGORITHM], audience=JWT_AUDIENCE)
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
