"""
Public interface of the reminders domain — the only module outside it
allowed to import from app.domains.reminders (besides its api.py).

Current consumers:
    - the chat (orchestrator/turn_service.py) gives the assistant the user's
      application dates with deadlines_text().
"""

from __future__ import annotations

from app.domains.reminders.service import deadlines_text, list_reminders

__all__ = ["deadlines_text", "list_reminders"]
