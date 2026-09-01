from __future__ import annotations

from app.domains.course_catalog import repository


def list_courses() -> list[dict]:
    return repository.list_all()
