"""
User profile repository — pure data access (no LLM calls) for
`student.user_profiles`. Lives in the same Supabase project as every other
domain's per-user tables (conversation_db) but in the `student` schema.

`student.user_profiles.user_id` is PK + FK -> student.users(user_id), so a
row must already exist in student.users (see the auth domain) before a
profile can be written.
"""

from __future__ import annotations

from app.adapters.conversation_db_adapter import conversation_db
from app.domains.profile.constants import PROFILE_FIELDS


def get(user_id: str) -> dict | None:
    cols = ", ".join(PROFILE_FIELDS)
    row = conversation_db.fetch_one(f"select {cols} from student.user_profiles where user_id = %s", (user_id,))
    if not row:
        return None
    return dict(zip(PROFILE_FIELDS, row))


def upsert(user_id: str, fields: dict) -> dict:
    """Full overwrite (not a merge): every column in PROFILE_FIELDS is set
    explicitly from `fields`, defaulting to NULL when absent, so uploading a
    new résumé fully replaces the previous profile rather than accumulating
    facts across uploads."""
    values = [fields.get(col) for col in PROFILE_FIELDS]
    col_list = ", ".join(PROFILE_FIELDS)
    placeholders = ", ".join(["%s"] * len(PROFILE_FIELDS))
    update_clause = ", ".join(f"{col} = excluded.{col}" for col in PROFILE_FIELDS)

    conversation_db.execute(
        f"""
        insert into student.user_profiles (user_id, {col_list}, updated_at)
        values (%s, {placeholders}, now())
        on conflict (user_id) do update
          set {update_clause}, updated_at = now()
        """,
        [user_id] + values,
    )
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

    updated_row = conversation_db.execute_returning(
        f"""
        update student.user_profiles
           set {assignments}, updated_at = now()
         where user_id = %s
         returning user_id
        """,
        values + [user_id],
    )
    if updated_row is None:
        return None
    return get(user_id)
