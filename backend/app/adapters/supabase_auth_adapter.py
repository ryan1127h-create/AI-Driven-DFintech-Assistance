"""
Supabase Auth adapter for AuthPort. Two lazily-built clients, on purpose:
admin operations (create_user, sign_out-by-token) need the service_role key
the same way supabase_storage_adapter.py's uploads do, but the actual
password check (sign_in_with_password) is a public GoTrue endpoint meant to
be called with the anon key — using service_role there would work but skips
the provider's own per-key rate limiting on login attempts.
"""

from __future__ import annotations

from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from app.core.config import settings
from app.ports.auth_port import AuthenticationError, AuthSession, AuthPort


class SupabaseAuthAdapter(AuthPort):
    def __init__(self, url: str, service_key: str, anon_key: str) -> None:
        self._url = url
        self._service_key = service_key
        self._anon_key = anon_key
        self._admin_client: Client | None = None
        self._anon_client: Client | None = None

    def _get_admin_client(self) -> Client:
        if self._admin_client is None:
            self._admin_client = create_client(self._url, self._service_key)
        return self._admin_client

    def _get_anon_client(self) -> Client:
        if self._anon_client is None:
            self._anon_client = create_client(self._url, self._anon_key)
        return self._anon_client

    def create_user(self, email: str, password: str, full_name: str) -> str:
        response = self._get_admin_client().auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # our own 6-digit code already proved ownership
            "user_metadata": {"full_name": full_name},
        })
        return response.user.id

    def sign_in(self, email: str, password: str) -> AuthSession:
        try:
            response = self._get_anon_client().auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
        except AuthApiError as exc:
            raise AuthenticationError(str(exc)) from exc

        session = response.session
        if session is None or response.user is None:
            raise AuthenticationError("Supabase Auth did not return a session.")
        return AuthSession(
            user_id=response.user.id,
            access_token=session.access_token,
            expires_in=session.expires_in,
        )

    def sign_out(self, access_token: str) -> None:
        self._get_admin_client().auth.admin.sign_out(access_token, "global")


auth_provider = SupabaseAuthAdapter(settings.supabase_url, settings.supabase_service_key, settings.supabase_anon_key)
