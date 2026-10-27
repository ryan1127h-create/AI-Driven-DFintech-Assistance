"""
Contract for the identity provider that owns account creation, password
storage/verification, and session issuance/revocation. Supabase Auth
(auth.users) is the only implementation — the password itself never lives
in this app's own database; every other domain's user_id foreign keys point
at the id this port hands back (see app/domains/auth/repository.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AuthSession:
    user_id: str
    access_token: str
    expires_in: int


class AuthenticationError(Exception):
    """Raised by sign_in() for invalid credentials — distinct from an
    unexpected provider/network failure, so callers can map it to a clear
    401 instead of a generic 503."""


class AuthPort(Protocol):
    def create_user(self, email: str, password: str, full_name: str) -> str:
        """Creates a new account with the provider and returns its user_id.
        Called only after this app's own email-ownership check (the 6-digit
        code flow) has already passed, so the account is created
        pre-confirmed — the provider never needs to send its own
        confirmation email."""
        ...

    def update_full_name(self, user_id: str, full_name: str) -> None:
        """Updates the name kept in the provider's user metadata."""
        ...

    def update_password(self, user_id: str, password: str) -> None:
        """Sets a new password, after this app's own reset code has proved
        the user owns the account's email."""
        ...

    def delete_user(self, user_id: str) -> None:
        """Deletes the provider's user. The account row and everything that
        references it go with it through ON DELETE CASCADE."""
        ...

    def sign_in(self, email: str, password: str) -> AuthSession:
        """Verifies the password and returns a new session. Raises
        AuthenticationError for invalid credentials."""
        ...

    def sign_out(self, access_token: str) -> None:
        """Revokes the session's refresh token so it can no longer be
        renewed. Raises on failure — the caller decides whether that should
        block logout (see app/domains/auth/service.py, which treats this as
        best-effort the same way it already does for its own Redis
        blacklist write)."""
        ...
