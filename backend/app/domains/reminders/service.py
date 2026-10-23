"""
In-app reminders: what an applicant should act on next, worked out from
the school's current records on every read — no scheduler, so a reminder
is never out of date with the application it is about.

    draft          the application is still a draft: submit it before the
                   application period closes (urgent within 30 days)
    missing_docs   required documents the school hasn't received (urgent
                   once review is paused for them, DOCS_REQUIRED)
    offer_deadline an offer to accept before it expires (urgent within 7
                   days); none once it has expired

A reminder's key names the situation it is about (the application, the
missing documents, the date), so closing one hides only that situation: a
new missing document or a new deadline brings it back.

Closed reminders are kept with the account (auth's account.reminder_dismissals).

deadlines_text() gives the assistant the same dates, so "when must I accept
my offer?" is answered from the record.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domains.auth import interface as auth
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.program_catalog import interface as program_catalog
from app.domains.sis import interface as sis

# Dates are the school's: Singapore time.
SCHOOL_TZ = ZoneInfo("Asia/Singapore")
_DRAFT_URGENT_DAYS = 30
_OFFER_URGENT_DAYS = 7
_REVIEW_STATUSES = ("SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED")


def _today() -> date:
    return datetime.now(SCHOOL_TZ).date()


def _fmt(day: date) -> str:
    return f"{day.day} {day:%b %Y}"


def _fmt_long(day: date) -> str:
    """For the assistant's context: the figure check reads full month names."""
    return f"{day.day} {day:%B %Y}"


def _days(n: int) -> str:
    return "today" if n == 0 else f"{n} day{'s' if n != 1 else ''} left"


def _application_closes(today: date) -> date | None:
    """The next closing date of MSc DFT's application period."""
    target = next((p for p in program_catalog.list_programs() if p["is_target"]), None)
    closing = sorted(d["closes_on"] for d in (target or {}).get("deadlines", []) if d.get("closes_on") and d["closes_on"] >= today)
    return closing[0] if closing else None


def _offer_expiry(app: dict) -> date | None:
    expires = app.get("offer_expires_at")
    return expires.astimezone(SCHOOL_TZ).date() if expires else None


def _draft(app: dict, closes: date | None, today: date) -> dict:
    body = "Only submitted applications are reviewed."
    days = (closes - today).days if closes else None
    if closes:
        body = f"Submit it by {_fmt(closes)} ({_days(days)}). " + body
    return {
        "key": f"draft:{app['application_id']}:{closes or ''}", "kind": "draft",
        "title": f"Application {app['application_no']} is still a draft", "body": body,
        "due_date": closes, "urgent": days is not None and days <= _DRAFT_URGENT_DAYS,
        "action": {"label": "Open checklist", "to": "/workspace/checklist"},
    }


def _missing_docs(app: dict, items: dict) -> dict | None:
    missing = [d["item_key"] for d in app.get("documents", []) if not d["submitted"]]
    paused = app["status"] == "DOCS_REQUIRED"
    # Optional or conditional items only count once the school has asked for more.
    shown = missing if paused else [k for k in missing if (items.get(k) or {}).get("required")]
    if not shown:
        return None
    labels = [(items.get(k) or {}).get("label") or k.replace("_", " ") for k in shown]
    return {
        "key": f"docs:{app['application_id']}:{','.join(sorted(shown))}", "kind": "missing_docs",
        "title": f"{len(shown)} document{'s' if len(shown) != 1 else ''} still missing for {app['application_no']}",
        "body": ("Review is paused until they arrive: " if paused else "Not received yet: ") + "; ".join(labels) + ".",
        "due_date": None, "urgent": paused,
        "action": {"label": "Open checklist", "to": "/workspace/checklist"},
    }


def _offer(app: dict, today: date) -> dict | None:
    expires = _offer_expiry(app)
    if expires is None or expires < today:
        return None
    days = (expires - today).days
    return {
        "key": f"offer:{app['application_id']}:{expires}", "kind": "offer_deadline",
        "title": f"Accept your offer by {_fmt(expires)}",
        "body": f"Your offer for {app['application_no']} expires on {_fmt(expires)} ({_days(days)}). "
                "Accept it in the Graduate Admission System.",
        "due_date": expires, "urgent": days <= _OFFER_URGENT_DAYS,
        "action": {"label": "How to accept", "prompt": "How do I accept my offer?"},
    }


def _all_reminders(user_id: str, today: date) -> list[dict]:
    applications = sis.list_applications(user_id)
    if not applications:
        return []
    items = knowledge.list_admissions_items()
    closes = _application_closes(today) if any(a["status"] == "DRAFT" for a in applications) else None
    found = []
    for app in applications:
        if app["status"] == "DRAFT":
            found.append(_draft(app, closes, today))
        elif app["status"] in _REVIEW_STATUSES:
            found.append(_missing_docs(app, items))
        elif app["status"] == "OFFER":
            found.append(_offer(app, today))
    return [r for r in found if r]


def list_reminders(user_id: str, today: date | None = None) -> list[dict]:
    """The user's open reminders, urgent first, then by due date."""
    today = today or _today()
    closed = auth.dismissed_reminder_keys(user_id)
    reminders = [r for r in _all_reminders(user_id, today) if r["key"] not in closed]
    reminders.sort(key=lambda r: (not r["urgent"], r["due_date"] or date.max))
    return [{**r, "due_date": r["due_date"].isoformat() if r["due_date"] else None} for r in reminders]


def dismiss(user_id: str, key: str) -> None:
    auth.dismiss_reminder(user_id, key)


def deadlines_text(user_id: str, today: date | None = None) -> str | None:
    """The user's own application dates as plain lines for the assistant's
    context (dismissed or not); None when there are none."""
    today = today or _today()
    lines = []
    for app in sis.list_applications(user_id):
        expires = _offer_expiry(app)
        if app["status"] == "OFFER" and expires:
            state = "expired" if expires < today else _days((expires - today).days)
            lines.append(f"- Offer for {app['application_no']} must be accepted by {_fmt_long(expires)} ({state}).")
        elif app["status"] == "DRAFT":
            closes = _application_closes(today)
            if closes:
                lines.append(f"- Application {app['application_no']} is a draft; the application period closes on "
                             f"{_fmt_long(closes)} ({_days((closes - today).days)}).")
    if not lines:
        return None
    return "Application dates (from the school's record):\n" + "\n".join(lines)
