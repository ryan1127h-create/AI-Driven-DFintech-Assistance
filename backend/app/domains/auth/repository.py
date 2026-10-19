"""
Data access for `account.accounts` and `account.user_settings` — no
password hashing, no JWT, no HTTP concerns (see security.py and service.py
for those).

Rows are created by the `on_auth_user_created` trigger on auth.users
(account, settings and an empty profile, role 'user', full_name from
user_metadata), so there is deliberately no create function — creating the
Supabase Auth user is what creates the account. Every other domain's
user_id foreign keys point at account.accounts.
"""

from __future__ import annotations

from app.adapters.account_db_adapter import account_db

ROLES = ("user", "admin")
ACCOUNT_STATUSES = ("active", "disabled")
ANSWER_DEPTHS = ("concise", "standard", "detailed")
# The profile welcome questionnaire: not_started (offer it), skipped (remind
# on the chat page instead) or completed.
ONBOARDING_STATUSES = ("not_started", "skipped", "completed")

_ACCOUNT_SELECT = """
    select user_id, email, full_name, account_status, role, is_anonymous,
           last_login_at, created_at
      from account.accounts
"""

_SETTINGS_COLUMNS = ("language_pref", "answer_depth", "email_notifications")


def get_account(user_id: str) -> dict | None:
    return account_db.fetch_one_dict(_ACCOUNT_SELECT + " where user_id = %s", (user_id,))


def get_account_by_email(email: str) -> dict | None:
    return account_db.fetch_one_dict(_ACCOUNT_SELECT + " where email = %s", (email,))


def get_accounts(user_ids: list[str]) -> list[dict]:
    if not user_ids:
        return []
    return account_db.fetch_all_dict(_ACCOUNT_SELECT + " where user_id = any(%s::uuid[])", (list(user_ids),))


def touch_last_login(user_id: str) -> None:
    account_db.execute(
        "update account.accounts set last_login_at = now(), updated_at = now() where user_id = %s",
        (user_id,),
    )


def set_full_name(user_id: str, full_name: str) -> bool:
    """Returns False if no such account."""
    row = account_db.execute_returning(
        "update account.accounts set full_name = %s, updated_at = now() where user_id = %s returning user_id",
        (full_name, user_id),
    )
    return row is not None


def set_role(user_id: str, role: str) -> bool:
    """Returns False if no such account."""
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    row = account_db.execute_returning(
        "update account.accounts set role = %s, updated_at = now() where user_id = %s returning user_id",
        (role, user_id),
    )
    return row is not None


def set_status(user_id: str, status: str) -> bool:
    """Returns False if no such account."""
    if status not in ACCOUNT_STATUSES:
        raise ValueError(f"unknown account status: {status}")
    row = account_db.execute_returning(
        "update account.accounts set account_status = %s, updated_at = now() where user_id = %s returning user_id",
        (status, user_id),
    )
    return row is not None


def get_settings(user_id: str) -> dict | None:
    return account_db.fetch_one_dict(
        f"select {', '.join(_SETTINGS_COLUMNS)}, updated_at from account.user_settings where user_id = %s",
        (user_id,),
    )


def get_onboarding_status(user_id: str) -> str | None:
    """None if the user has no settings row (i.e. no account)."""
    row = account_db.fetch_one_dict(
        "select onboarding_status from account.user_settings where user_id = %s", (user_id,)
    )
    return row["onboarding_status"] if row else None


def set_onboarding_status(user_id: str, status: str) -> bool:
    """Returns False if the user has no settings row."""
    if status not in ONBOARDING_STATUSES:
        raise ValueError(f"unknown onboarding status: {status}")
    row = account_db.execute_returning(
        "update account.user_settings set onboarding_status = %s, updated_at = now() where user_id = %s returning user_id",
        (status, user_id),
    )
    return row is not None


def update_settings(user_id: str, fields: dict) -> dict | None:
    """Updates only the provided settings. Returns None if the user has no
    settings row (i.e. no account)."""
    updates = {k: v for k, v in fields.items() if k in _SETTINGS_COLUMNS}
    if "answer_depth" in updates and updates["answer_depth"] not in ANSWER_DEPTHS:
        raise ValueError(f"unknown answer_depth: {updates['answer_depth']}")
    if not updates:
        return get_settings(user_id)

    assignments = ", ".join(f"{col} = %s" for col in updates)
    return account_db.fetch_one_dict(
        f"""
        update account.user_settings
           set {assignments}, updated_at = now()
         where user_id = %s
         returning {', '.join(_SETTINGS_COLUMNS)}, updated_at
        """,
        [*updates.values(), user_id],
    )
