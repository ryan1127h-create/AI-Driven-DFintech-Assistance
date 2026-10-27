"""
Contract for sending a single transactional email. Nothing above this port
(auth's service.py, specifically) knows or cares which provider actually
delivers it.
"""

from __future__ import annotations

from typing import Protocol


class EmailPort(Protocol):
    def send(self, to: str, subject: str, text_body: str) -> None:
        """Sends one plain-text email. Raises on delivery failure — callers
        that want a degraded fallback (e.g. logging the content instead of
        blocking a request) decide that for themselves, since not every
        caller wants the same behavior."""
        ...
