"""Data access for the raw course catalog — a thin pass-through to the
knowledge base's `app.courses` table (see adapters/knowledge_db_adapter.py),
with no filtering or transformation of its own."""

from __future__ import annotations

from app.adapters.knowledge_db_adapter import knowledge_db


def list_all() -> list[dict]:
    return knowledge_db.fetch_all_courses()
