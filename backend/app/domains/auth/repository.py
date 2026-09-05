"""
Data access for `student.users` — no hashing, no JWT, no HTTP concerns
(see security.py and service.py for those). Every other domain's user_id
foreign keys point at this same table.
"""

from __future__ import annotations

from app.adapters.conversation_db_adapter import conversation_db

_COLUMNS = ("user_id", "email", "full_name", "account_status", "password_hash", "role")


def _row_to_dict(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return dict(zip(_COLUMNS, row))


def get_by_email(email: str) -> dict | None:
    row = conversation_db.fetch_one(
        f"select {', '.join(_COLUMNS)} from student.users where email = %s",
        (email,),
    )
    return _row_to_dict(row)


def get_by_id(user_id: str) -> dict | None:
    row = conversation_db.fetch_one(
        f"select {', '.join(_COLUMNS)} from student.users where user_id = %s",
        (user_id,),
    )
    return _row_to_dict(row)


def create(email: str, password_hash: str, full_name: str, role: str) -> dict:
    row = conversation_db.execute_returning(
        """
        insert into student.users (email, password_hash, full_name, account_status, role)
        values (%s, %s, %s, 'active', %s)
        returning user_id, email, full_name, account_status, password_hash, role
        """,
        (email, password_hash, full_name, role),
    )
    return _row_to_dict(row)


def update_last_login(user_id: str) -> None:
    conversation_db.execute(
        "update student.users set last_login_at = now(), updated_at = now() where user_id = %s",
        (user_id,),
    )
