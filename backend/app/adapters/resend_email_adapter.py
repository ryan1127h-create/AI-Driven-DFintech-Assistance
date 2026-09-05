"""
Resend adapter for EmailPort — a plain HTTPS POST via httpx (already a
dependency for other adapters; no new SDK needed for one endpoint).

When RESEND_API_KEY isn't set, send() prints the email to the server log
instead of raising or silently dropping it — a deliberate dev-mode
fallback so registration/email-verification is testable without a Resend
account. This is not a fallback for a delivery failure once a key *is*
configured — a real API error still raises, since a caller that's counting
on the email actually reaching someone (auth's verification-code flow)
needs to know it didn't.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.ports.email_port import EmailPort

logger = get_logger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailAdapter(EmailPort):
    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from_address = from_address

    def send(self, to: str, subject: str, text_body: str) -> None:
        if not self._api_key:
            logger.info("RESEND_API_KEY not set — printing email instead of sending it.")
            print(f"\n----- [dev-mode email] to={to} subject={subject!r} -----\n{text_body}\n" + "-" * 40 + "\n")
            return

        response = httpx.post(
            _RESEND_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"from": self._from_address, "to": [to], "subject": subject, "text": text_body},
            timeout=10.0,
        )
        response.raise_for_status()


email = ResendEmailAdapter(settings.resend_api_key, settings.email_from_address)
