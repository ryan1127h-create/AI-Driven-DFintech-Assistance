"""
Public interface of the auth domain — the only module other domains (and
the orchestrator) are allowed to import from app.domains.auth.
Everything else in this package (repository, security, service internals)
is private.

Usage:
    from app.domains.auth.interface import get_current_user_id

    @router.get("", response_model=ProfileOut)
    async def get_profile(user_id: str = Depends(get_current_user_id)):
        ...
"""

from __future__ import annotations

from app.domains.auth import repository
from app.domains.auth.service import get_current_user_id

__all__ = ["get_assistant_preferences", "get_current_user_id", "get_login_email"]


def get_login_email(user_id: str) -> str | None:
    """The email the user logs in with, or None if there is no account."""
    account = repository.get_account(user_id)
    return account["email"] if account else None


def get_assistant_preferences(user_id: str) -> dict:
    """{"language_pref": [codes, in order], "answer_depth": str} from the
    user's settings; the defaults ([] and "standard") when there are none
    or they can't be read — a preference must never break a chat turn."""
    try:
        settings_row = repository.get_settings(user_id) or {}
    except Exception:
        settings_row = {}
    return {
        "language_pref": list(settings_row.get("language_pref") or []),
        "answer_depth": settings_row.get("answer_depth") or "standard",
    }
