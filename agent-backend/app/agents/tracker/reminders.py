"""#5 Reminder logic: milestone nudges with consent, prefs, and frequency control.

Deterministic. Reminders are milestone-driven: each deadline maps to a milestone
that only fires in the relevant application status (status gating), within a lead
window. Respects notification preferences (channels + off switch) and consent,
and de-duplicates already-sent reminders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from common.notifier import Notifier, get_notifier
from common.profile import NotificationFrequency, NotificationRecord, StatusCode, UserProfile


@dataclass
class Reminder:
    key: str
    name: str
    date: str  # ISO
    message: str
    urgency: str  # "info" | "soon" | "urgent"
    channels: list[str] = field(default_factory=list)


# Per milestone: lead window (days), the status it applies to (None = any while
# the application is active), and a label.
_MILESTONES = {
    "application_deadline": {"lead": 21, "status": None, "label": "submit application materials"},
    "document_deadline": {"lead": 21, "status": StatusCode.DOCS_REQUIRED, "label": "submit supplementary materials"},
    "offer_acceptance": {"lead": 14, "status": StatusCode.OFFER, "label": "confirm offer acceptance"},
    "registration": {"lead": 14, "status": StatusCode.ACCEPTED, "label": "complete registration"},
}


def _urgency(days_left: int) -> str:
    if days_left <= 3:
        return "urgent"
    if days_left <= 7:
        return "soon"
    return "info"


def build_reminders(
    profile: UserProfile,
    today: date | None = None,
    already_sent: set[str] | None = None,
) -> list[Reminder]:
    """Return reminders to show now (milestone + status gated, prefs honoured)."""
    if not profile.consent_flags.reminders:
        return []
    if profile.notification_prefs.frequency == NotificationFrequency.off:
        return []  # user turned notifications off
    if profile.application is None:
        return []

    today = today or date.today()
    already_sent = already_sent or set()
    channels = [c.value for c in profile.notification_prefs.channels]
    status = profile.application.status_code
    reminders: list[Reminder] = []

    for name, iso in profile.application.deadlines.items():
        ms = _MILESTONES.get(name, {"lead": 14, "status": None, "label": name})
        if name in profile.notification_prefs.muted_milestones:
            continue  # user muted this milestone type
        if ms["status"] is not None and ms["status"] != status:
            continue  # milestone not active in the current status
        try:
            days_left = (date.fromisoformat(iso) - today).days
        except ValueError:
            continue
        if days_left < 0 or days_left > ms["lead"]:
            continue  # outside the nudging window
        key = f"{name}:{iso}"
        if key in already_sent:
            continue  # frequency control
        reminders.append(
            Reminder(
                key=key,
                name=name,
                date=iso,
                message=_message_for(name, ms["label"], days_left, status),
                urgency=_urgency(days_left),
                channels=channels,
            )
        )
    return reminders


def _message_for(name: str, label: str, days_left: int, status: StatusCode) -> str:
    if name in ("document_deadline", "application_deadline") and status == StatusCode.DOCS_REQUIRED:
        return f"Your application is on hold because materials are missing. Please {label} within {days_left} days."
    return f"There are {days_left} days left before the deadline to {label}; please handle it in time."


@dataclass
class Notification:
    kind: str                 # "single" | "digest"
    channels: list[str]
    date: str                 # ISO (today)
    subject: str
    message: str
    urgency: str              # info | soon | urgent (digest takes the most urgent)
    reminder_keys: list[str]


_URGENCY_RANK = {"info": 0, "soon": 1, "urgent": 2}
_SUBJECT_PREFIX = "NUS MSc DFinTech Reminder"


def due_now(profile: UserProfile, today: date | None = None) -> list[Notification]:
    """What should be delivered now: relevant reminders minus already-logged ones,
    shaped by frequency. Pure read — does NOT mutate the profile."""
    today = today or date.today()
    candidates = build_reminders(profile, today=today)  # consent/off/mute/window/status gated
    if not candidates:
        return []
    sent = {rec.key for rec in profile.notification_log}
    pending = [r for r in candidates if r.key not in sent]
    if not pending:
        return []
    channels = [c.value for c in profile.notification_prefs.channels]
    iso_today = today.isoformat()
    if profile.notification_prefs.frequency == NotificationFrequency.daily_digest:
        urgency = max((r.urgency for r in pending), key=lambda u: _URGENCY_RANK.get(u, 0))
        body = "You have the following pending reminders:\n" + "\n".join(f"- {r.message}" for r in pending)
        return [Notification(
            kind="digest", channels=channels, date=iso_today,
            subject=f"{_SUBJECT_PREFIX}: {len(pending)} pending item(s)",
            message=body, urgency=urgency,
            reminder_keys=[r.key for r in pending],
        )]
    return [
        Notification(
            kind="single", channels=channels, date=iso_today,
            subject=f"{_SUBJECT_PREFIX}:{_MILESTONES.get(r.name, {}).get('label', r.name)}",
            message=r.message, urgency=r.urgency, reminder_keys=[r.key],
        )
        for r in pending
    ]


def dispatch_due(profile: UserProfile, today: date | None = None,
                 notifier: Notifier | None = None) -> list[Notification]:
    """Deliver due notifications and record them on the profile (mutates the log).

    Email channel sends via the notifier only when the profile has an email
    address; in-app is record-only. A failed real send is still recorded (with
    delivered=False) so it is not retried and remains auditable."""
    today = today or date.today()
    notifier = notifier or get_notifier()
    notes = due_now(profile, today=today)
    for n in notes:
        delivered = True
        if "email" in n.channels and profile.email:
            ok = notifier.send(profile.email, n.subject, n.message)
            delivered = delivered and ok
        for key in n.reminder_keys:  # digest records each sub-key -> only-once across frequencies
            profile.notification_log.append(NotificationRecord(
                key=key, date=n.date, channels=list(n.channels), delivered=delivered,
            ))
    return notes
