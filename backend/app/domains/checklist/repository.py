"""
Persistence for checklist item state. The checklist items themselves are
defined in service.py; this repository only stores per-user status
overrides, keeping the HTTP contract independent of how (or whether) a
given item is backed by an actual upload.
"""

from __future__ import annotations

from app.adapters.conversation_db_adapter import conversation_db

_WRITE_COLUMNS = {
    "status",
    "evidence_source",
    "note",
    "file_name",
    "content_type",
    "file_size",
    "storage_path",
    "uploaded_at",
}


def list_items(user_id: str) -> dict[str, dict]:
    """Returns item_id -> persisted state for the user."""
    rows = conversation_db.fetch_all(
        """
        select item_id, status, evidence_source, note,
               file_name, content_type, file_size, storage_path,
               uploaded_at, updated_at
          from student.application_checklist_items
         where user_id = %s
        """,
        (user_id,),
    )
    return {
        row[0]: {
            "status": row[1],
            "evidence_source": row[2],
            "note": row[3],
            "file_name": row[4],
            "content_type": row[5],
            "file_size": row[6],
            "storage_path": row[7],
            "uploaded_at": row[8],
            "updated_at": row[9],
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
    update_assignments = ", ".join(f"{col} = excluded.{col}" for col in updates) or "updated_at = now()"
    values = [user_id, item_id, *insert_values.values()]

    conversation_db.execute(
        f"""
        insert into student.application_checklist_items
            ({", ".join(columns)}, updated_at)
        values ({placeholders}, now())
        on conflict (user_id, item_id) do update
           set {update_assignments}, updated_at = now()
        """,
        values,
    )
