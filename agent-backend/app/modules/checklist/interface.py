"""
Public interface of the checklist module — the ONLY file other modules are
allowed to import from app.modules.checklist. Everything else in this
package (repository, service internals) is private to this module.

Current consumers:
    - profile::api.py uses get_uploaded_file(RESUME_ITEM_ID, user_id) to
      pull the checklist's "CV" upload for résumé extraction.

Usage (see app/modules/profile/api.py):
    from app.modules.checklist import interface as checklist_interface
    content, file_name, content_type = await checklist_interface.get_uploaded_file(
        checklist_interface.RESUME_ITEM_ID, user_id
    )
"""

from __future__ import annotations

from app.modules.checklist import service
from app.modules.profile.interface import TEST_USER_ID

__all__ = ["RESUME_ITEM_ID", "get_uploaded_file"]

# The checklist item_id that other modules should treat as "the resume" —
# single source of truth so this string isn't hardcoded again elsewhere.
RESUME_ITEM_ID = "cv"


async def get_uploaded_file(
    item_id: str, user_id: str = TEST_USER_ID
) -> tuple[bytes, str, str] | None:
    """Returns (content, file_name, content_type) for a previously uploaded
    checklist item's file, or None if nothing has been uploaded for it yet.
    Wraps service.download_checklist_file()'s ValueError (item_id unknown or
    nothing uploaded) so callers don't need to know checklist's internal
    exception vocabulary."""
    try:
        return await service.download_checklist_file(item_id, user_id)
    except ValueError:
        return None
