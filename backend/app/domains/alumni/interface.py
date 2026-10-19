"""
Public interface of the alumni domain — the only module other domains are
allowed to import from app.domains.alumni.

Current consumers:
    - admin manages the alumni directory with the staff_* functions (staff
      authorisation is admin's own check).
"""

from __future__ import annotations

from app.domains.alumni.service import expertise_options, staff_create, staff_delete, staff_list, staff_update

__all__ = ["expertise_options", "staff_create", "staff_delete", "staff_list", "staff_update"]
