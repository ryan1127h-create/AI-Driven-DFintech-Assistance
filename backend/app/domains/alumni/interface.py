"""
Public interface of the alumni domain — the only module other domains are
allowed to import from app.domains.alumni.

Current consumers:
    - admin manages the alumni directory with the staff_* functions (staff
      authorisation is admin's own check).
    - the chat's alumni tool (tools/specialist/alumni_match_tool.py) lists
      a student's matches with list_matches, under the same student-only
      check as the Alumni Match page.
    - the chat adds alumni stories to answers (tools/alumni_stories.py),
      only from alumni who chose to share with that audience.
"""

from __future__ import annotations

from app.domains.alumni.service import (
    expertise_options,
    list_matches,
    staff_create,
    staff_delete,
    staff_list,
    staff_update,
    stories,
)

__all__ = ["expertise_options", "list_matches", "staff_create", "staff_delete", "staff_list", "staff_update",
           "stories"]
