"""Persistence for checklist item state.

The checklist items themselves are defined in service.py. This repository only
stores per-user status overrides, keeping the HTTP contract independent from a
future document-upload implementation.
"""

from __future__ import annotations

from app.clients.postgres_client import LazyPostgresConnection
from app.core.config import settings

_conn = LazyPostgresConnection(settings.conversation_database_url)

_WRITE_COLUMNS = {
    "status",
    "evidence_source",
    "note",
    "file_name",
    "content_type",
    "file_size",
    "storage_path",
    "file_content",
    "uploaded_at",
}


def list_items(user_id: str) -> dict[str, dict]:
    """Returns item_id -> persisted state for the user."""
    conn = _conn.get()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select item_id, status, evidence_source, note,
                       file_name, content_type, file_size, uploaded_at, updated_at
                  from student.application_checklist_items
                 where user_id = %s
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    except Exception:
        conn.rollback()
        raise
    return {
        row[0]: {
            "status": row[1],
            "evidence_source": row[2],
            "note": row[3],
            "file_name": row[4],
            "content_type": row[5],
            "file_size": row[6],
            "uploaded_at": row[7],
            "updated_at": row[8],
        }
        for row in rows
    }


def upsert_item(user_id: str, item_id: str, fields: dict) -> None:
    """Creates or updates one persisted checklist item state."""
    updates = {k: v for k, v in fields.items() if k in _WRITE_COLUMNS}
    insert_values = dict(updates)
    insert_values.setdefault("status", "not_started")

    columns = ["user_id", "item_id", *insert_values]
    placeholders = ", ".join(["%s"] * len(columns))
    update_assignments = ", ".join(
        f"{col} = excluded.{col}" for col in updates
    ) or "updated_at = now()"
    values = [user_id, item_id, *insert_values.values()]

    conn = _conn.get()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                insert into student.application_checklist_items
                    ({", ".join(columns)}, updated_at)
                values ({placeholders}, now())
                on conflict (user_id, item_id) do update
                   set {update_assignments}, updated_at = now()
                """,
                values,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
