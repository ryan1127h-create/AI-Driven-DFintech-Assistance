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


@pytest.fixture(autouse=True)
def stored_cases(monkeypatch):
    """Likewise for escalation cases: an in-memory chat.cases, so a test
    turn that escalates never writes to the shared table."""
    import itertools
    from datetime import datetime, timezone

    from app.domains.conversation import service as conversation_service

    rows: list[dict] = []
    ids = itertools.count(1)

    def insert_case(case):
        if any(r["conversation_id"] == case["conversation_id"] and r["category"] == case["category"]
               and r["status"] == "open" for r in rows):
            return None
        row = {**case, "id": f"00000000-0000-0000-0000-{next(ids):012d}", "status": "open",
               "created_at": datetime.now(timezone.utc), "resolved_at": None}
        rows.append(row)
        return row

    def find_open_case(conversation_id, category):
        return next((r for r in rows if r["conversation_id"] == conversation_id and r["category"] == category
                     and r["status"] == "open"), None)

    monkeypatch.setattr(conversation_service, "insert_case", insert_case)
    monkeypatch.setattr(conversation_service, "find_open_case", find_open_case)
    monkeypatch.setattr(conversation_service, "list_cases_for_user",
                        lambda user_id: [r for r in rows if r["user_id"] == user_id])
    return rows


@pytest.fixture(autouse=True)
def no_alumni_stories(monkeypatch):
    """A test turn about careers would otherwise read the shared alumni
    directory for stories to add; tests of the stories set their own."""
    from app.tools import alumni_stories

    monkeypatch.setattr(alumni_stories.alumni, "stories", lambda audience, interests, limit=2: [])
    monkeypatch.setattr(alumni_stories, "get_profile_for_purpose", lambda user_id, purpose: {})
