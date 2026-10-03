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
