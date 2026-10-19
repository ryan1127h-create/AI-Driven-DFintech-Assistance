"""Shared test setup."""

from __future__ import annotations

from collections import defaultdict

import pytest

from app.core import events


@pytest.fixture(autouse=True)
def no_event_handlers(monkeypatch):
    """Importing app.main registers the derived-label handlers; without this,
    any test that writes a profile would start real background recomputes."""
    monkeypatch.setattr(events, "_handlers", defaultdict(list))


@pytest.fixture(autouse=True)
def stored_turn_metrics(monkeypatch):
    """The test settings use the Supabase store, so a test that runs a chat
    turn would write a row to the shared chat.turn_metrics table. Every test
    gets an in-memory list instead (returned, for tests that check it), and
    the audience lookup doesn't read the real account table."""
    from app.domains.conversation import service as conversation_service
    from app.orchestrator import turn_service

    rows: list[dict] = []
    monkeypatch.setattr(conversation_service, "insert_turn_metric", rows.append)
    monkeypatch.setattr(turn_service, "get_audience", lambda user_id: "applicant")
    return rows
