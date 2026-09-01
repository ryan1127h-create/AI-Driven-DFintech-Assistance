"""
Public interface of the checklist domain — the only module other domains
are allowed to import from app.domains.checklist.

Current consumers:
    - profile reads the applicant's uploaded CV through
      get_uploaded_file(RESUME_ITEM_ID, user_id) rather than accepting its
      own separate résumé upload, so the two domains can never disagree
      about which file is current.

Usage:
    from app.domains.checklist import interface as checklist_interface
    content, file_name, content_type = await checklist_interface.get_uploaded_file(
        checklist_interface.RESUME_ITEM_ID, user_id
    )
"""

from __future__ import annotations

from app.core.errors import NotFoundError, ValidationError
from app.domains.checklist import service

__all__ = ["RESUME_ITEM_ID", "get_uploaded_file"]

# The checklist item_id other domains should treat as "the résumé" — a
# single source of truth so this string isn't hardcoded again elsewhere.
RESUME_ITEM_ID = "cv"


async def get_uploaded_file(item_id: str, user_id: str) -> tuple[bytes, str, str] | None:
    """Returns (content, file_name, content_type) for a previously uploaded
    checklist item's file, or None if nothing has been uploaded for it yet
    (or item_id isn't a real checklist item) — callers don't need to know
    checklist's internal exception vocabulary."""
    try:
        return await service.download_checklist_file(item_id, user_id)
    except (NotFoundError, ValidationError):
        return None
