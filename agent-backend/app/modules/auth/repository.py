"""
Auth repository — pure data access (no hashing, no JWT) for `student.users`
(see app/modules/auth/schema/user_password.sql for the password_hash column
this module added on top of the pre-existing table — see
app/modules/profile/schema/student_schema_clone.sql for the rest of it).

Lives in the same Supabase project/schema as app/modules/profile/repository.py
(CONVERSATION_DATABASE_URL, `student` schema) — every other module's
`user_id` foreign keys already point at this same table.
"""

from __future__ import annotations

from app.clients.postgres_client import LazyPostgresConnection
from app.core.config import settings

_conn = LazyPostgresConnection(settings.conversation_database_url)

_COLUMNS = ("user_id", "email", "full_name", "account_status", "password_hash")


def get_by_email(email: str) -> dict | None:
    with _conn.get().cursor() as cur:
        cur.execute(
            f"select {', '.join(_COLUMNS)} from student.users where email = %s",
            (email,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return dict(zip(_COLUMNS, row))


def get_by_id(user_id: str) -> dict | None:
    with _conn.get().cursor() as cur:
        cur.execute(
            f"select {', '.join(_COLUMNS)} from student.users where user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return dict(zip(_COLUMNS, row))


def create(email: str, password_hash: str, full_name: str) -> dict:
    conn = _conn.get()
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into student.users (email, password_hash, full_name, account_status)
            values (%s, %s, %s, 'active')
            returning user_id, email, full_name, account_status, password_hash
            """,
            (email, password_hash, full_name),
        )
        row = cur.fetchone()
    conn.commit()
    return dict(zip(_COLUMNS, row))


def update_last_login(user_id: str) -> None:
    conn = _conn.get()
    with conn.cursor() as cur:
        cur.execute(
            "update student.users set last_login_at = now(), updated_at = now() where user_id = %s",
            (user_id,),
        )
    conn.commit()
