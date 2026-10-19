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
from app.domains.auth.service import (
    delete_account, get_audience, get_current_user_id, set_account_status, update_full_name,
)

__all__ = [
    "delete_account", "find_user_id_by_email", "get_account_names", "get_assistant_preferences",
    "get_audience", "get_current_user_id", "get_login_email", "is_admin", "set_account_status",
    "update_full_name",
]


def get_account_names(user_ids: list[str]) -> dict[str, dict]:
    """{user_id: {"full_name", "email"}} for the accounts that exist."""
    return {
        str(row["user_id"]): {"full_name": row.get("full_name") or "", "email": row["email"]}
        for row in repository.get_accounts(user_ids)
    }


def find_user_id_by_email(email: str) -> str | None:
    """The account with this login email (case-insensitive), or None."""
    account = repository.get_account_by_email(email.strip().lower())
    return str(account["user_id"]) if account else None


def is_admin(user_id: str) -> bool:
    """True when the account exists, is active and has the admin role."""
    account = repository.get_account(user_id)
    return bool(account) and account.get("role") == "admin" and account.get("account_status") == "active"


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
