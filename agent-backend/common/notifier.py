"""Pluggable notification delivery seam.

The deterministic engine decides WHAT to send; a Notifier delivers it. This is
the "swap delivery on deployment" seam (cf. Retriever / Fetcher). Default is the
offline RecordingNotifier; configure SMTP credentials (common/config.py) to get
real email via SmtpEmailNotifier. Sending never raises — failures return False.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from common import config


class Notifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...


class RecordingNotifier:
    """Offline default: performs no external delivery (caller records the log)."""

    def send(self, to: str, subject: str, body: str) -> bool:
        return True


class SmtpEmailNotifier:
    """Sends plain-text email via stdlib smtplib. Returns False on any failure.

    Port 465 uses implicit SSL (SMTP_SSL) — required by 163/QQ-style servers.
    Other ports (e.g. 587) use plain SMTP then STARTTLS when use_tls is set.
    """

    def send(self, to: str, subject: str, body: str) -> bool:
        host = config.get_smtp_host()
        if not host or not to:
            return False
        msg = EmailMessage()
        msg["From"] = config.get_smtp_from() or config.get_smtp_username() or ""
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        port = config.get_smtp_port()
        try:
            server = (
                smtplib.SMTP_SSL(host, port, timeout=10)
                if port == 465
                else smtplib.SMTP(host, port, timeout=10)
            )
            with server:
                if port != 465 and config.get_smtp_use_tls():
                    server.starttls()
                username = config.get_smtp_username()
                password = config.get_smtp_password()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
            return True
        except Exception:
            return False


def get_notifier() -> Notifier:
    """SMTP notifier when credentials are configured, else the offline recorder."""
    return SmtpEmailNotifier() if config.smtp_configured() else RecordingNotifier()
