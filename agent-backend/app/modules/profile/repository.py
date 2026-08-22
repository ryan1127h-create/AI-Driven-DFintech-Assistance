"""
User profile repository — pure data access (no LLM calls) for the sandbox
`student.user_profiles` table (see
app/modules/profile/schema/student_schema_clone.sql). Lives in the same
Supabase project as the chatbot module's conversation storage
(CONVERSATION_DATABASE_URL) but in the separate `student` schema.

`student.user_profiles.user_id` is PK + FK -> student.users(user_id), so a
row must already exist in student.users before a profile can be written —
see app/modules/profile/schema/seed_test_user.sql.
"""

from __future__ import annotations

from app.clients.postgres_client import LazyPostgresConnection
from app.core.config import settings
from app.modules.profile.constants import PROFILE_FIELDS

_conn = LazyPostgresConnection(settings.conversation_database_url)


def get(user_id: str) -> dict | None:
    cols = ", ".join(PROFILE_FIELDS)
    with _conn.get().cursor() as cur:
        cur.execute(f"select {cols} from student.user_profiles where user_id = %s", (user_id,))
        row = cur.fetchone()
    if not row:
        return None
    return dict(zip(PROFILE_FIELDS, row))


def upsert(user_id: str, fields: dict) -> dict:
    """Full overwrite (not a merge): every column in PROFILE_FIELDS is set
    explicitly from `fields`, defaulting to NULL when absent, so uploading a
    new resume fully replaces the previous profile rather than accumulating
    facts across uploads."""
    values = [fields.get(col) for col in PROFILE_FIELDS]
    col_list = ", ".join(PROFILE_FIELDS)
    placeholders = ", ".join(["%s"] * len(PROFILE_FIELDS))
    update_clause = ", ".join(f"{col} = excluded.{col}" for col in PROFILE_FIELDS)

    conn = _conn.get()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            insert into student.user_profiles (user_id, {col_list}, updated_at)
            values (%s, {placeholders}, now())
            on conflict (user_id) do update
              set {update_clause}, updated_at = now()
            """,
            [user_id] + values,
        )
    conn.commit()
    return get(user_id)


def patch(user_id: str, fields: dict) -> dict | None:
    """Updates only the provided profile columns. Returns None if the
    profile row does not exist, so callers can surface a clear 404 instead
    of silently creating an incomplete profile."""
    updates = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
    if not updates:
        return get(user_id)

    assignments = ", ".join(f"{col} = %s" for col in updates)
    values = list(updates.values())

    conn = _conn.get()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            update student.user_profiles
               set {assignments}, updated_at = now()
             where user_id = %s
            """,
            values + [user_id],
        )
        updated = cur.rowcount
    conn.commit()
    if updated == 0:
        return None
    return get(user_id)
