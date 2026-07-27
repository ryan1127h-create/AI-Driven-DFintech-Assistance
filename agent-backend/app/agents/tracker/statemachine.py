"""#5 Mock application state machine + status translation.

Replaces the real admissions/CRM API for the MVP. Interface shape (get_status
returning code + deadlines + submitted docs) mirrors a real API so it can be
swapped later. State transitions are included to demo progression.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from common.profile import Application, StatusCode

_TRANS_PATH = Path(__file__).resolve().parents[3] / "data" / "status_translations.json"

# Allowed forward transitions (for demo / what-if).
_TRANSITIONS: dict[StatusCode, list[StatusCode]] = {
    StatusCode.DRAFT: [StatusCode.SUBMITTED],
    StatusCode.SUBMITTED: [StatusCode.UNDER_REVIEW, StatusCode.DOCS_REQUIRED],
    StatusCode.UNDER_REVIEW: [
        StatusCode.OFFER,
        StatusCode.WAITLIST,
        StatusCode.REJECTED,
        StatusCode.DOCS_REQUIRED,
    ],
    StatusCode.DOCS_REQUIRED: [StatusCode.UNDER_REVIEW],
    StatusCode.OFFER: [StatusCode.ACCEPTED],
    StatusCode.WAITLIST: [StatusCode.OFFER, StatusCode.REJECTED],
    StatusCode.REJECTED: [],
    StatusCode.ACCEPTED: [],
}


def _load_translations() -> dict:
    return json.loads(_TRANS_PATH.read_text(encoding="utf-8"))["translations"]


def translate(status: StatusCode) -> dict[str, str]:
    """Raw status code -> {human_status, next_step}. Pure rule mapping."""
    table = _load_translations()
    entry = table.get(status.value)
    if entry is None:
        return {"human_status": status.value, "next_step": "Please contact the admissions office for details."}
    return entry


def next_states(status: StatusCode) -> list[str]:
    return [s.value for s in _TRANSITIONS.get(status, [])]


def estimated_next_date(status: StatusCode, since: str | None) -> str | None:
    """Estimate when the next step happens: `since` date + the status's eta_days.

    Returns None when there's no eta for the status or no reference date.
    """
    entry = _load_translations().get(status.value, {})
    eta = entry.get("eta_days")
    if eta is None or not since:
        return None
    try:
        return (date.fromisoformat(since) + timedelta(days=int(eta))).isoformat()
    except ValueError:
        return None


def build_timeline(application: Application) -> list[dict]:
    """Translate the status history into a human-readable timeline (date-sorted)."""
    table = _load_translations()
    events = sorted(application.status_history, key=lambda e: e.date)
    out = []
    for e in events:
        entry = table.get(e.status_code.value, {})
        out.append({
            "status_code": e.status_code.value,
            "human_status": entry.get("human_status", e.status_code.value),
            "date": e.date,
            "note": e.note,
        })
    return out


def latest_status_date(application: Application) -> str | None:
    """Date the current status was reached (from history), if available."""
    matching = [e.date for e in application.status_history
                if e.status_code == application.status_code]
    if matching:
        return max(matching)
    if application.status_history:
        return max(e.date for e in application.status_history)
    return None
