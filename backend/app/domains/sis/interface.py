"""
Public interface of the sis domain — the only module other domains are
allowed to import from app.domains.sis.

Usage:
    from app.domains.sis import interface as sis
    record = sis.get_academic_record(user_id)
    current = sis.list_enrollments(user_id, status="current")
"""

from __future__ import annotations

from app.domains.sis.repository import (
    ENROLLMENT_SOURCES,
    ENROLLMENT_STATUSES,
    bind_application,
    delete_self_reported_enrollment,
    get_academic_record,
    get_program,
    list_applications,
    list_enrollments,
    unbind_application,
    upsert_enrollment,
)

__all__ = [
    "ENROLLMENT_SOURCES",
    "ENROLLMENT_STATUSES",
    "bind_application",
    "delete_self_reported_enrollment",
    "get_academic_record",
    "get_program",
    "list_applications",
    "list_enrollments",
    "unbind_application",
    "upsert_enrollment",
]
