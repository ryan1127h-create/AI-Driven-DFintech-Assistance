"""#5 Tracker Agent entry point.

Returns application status (translated), a status timeline, an estimated next
date, milestone reminders (preference-aware), and — when documents are required
— the specific outstanding items from the #4 checklist engine. Only *required*
items are reported as blocking; optional supporting material is listed separately.
"""
from __future__ import annotations

from datetime import date

from common.envelope import AgentResponse
from common.profile import NotificationChannel, NotificationFrequency, StatusCode, UserProfile

from .reminders import _MILESTONES, build_reminders, due_now
from .statemachine import (
    build_timeline,
    estimated_next_date,
    latest_status_date,
    next_states,
    translate,
)


_OUTSTANDING_STATUSES = ("missing", "rejected")
_LABEL_SEPARATOR = ", "  # output is English: no Chinese enumeration comma
_SENTENCE_SEPARATOR = ". "


def _document_dict(item) -> dict:
    return {"key": item.key, "label": item.label, "status": item.status}


def _split_outstanding_documents(profile: UserProfile) -> tuple[list[dict], list[dict]]:
    """Ask the #4 engine which items still need action, split by `required`.

    Only required items block the application. Optional supporting material is
    returned separately so the blocking list (and any count derived from it)
    matches the #4 checklist's `outstanding_count`.
    """
    from app.agents.checklist.engine import build_checklist

    result = build_checklist(profile)
    outstanding = [it for it in result.items if it.status in _OUTSTANDING_STATUSES]
    return (
        [_document_dict(it) for it in outstanding if it.required],
        [_document_dict(it) for it in outstanding if not it.required],
    )


def _material_completion_from_profile(profile: UserProfile) -> dict:
    """Summarise submitted/missing/rejected documents for the UI action centre."""
    from app.agents.checklist.engine import build_checklist

    result = build_checklist(profile)
    required = [it for it in result.items if it.required]
    submitted = [it for it in required if it.status in ("submitted", "under_review", "verified")]
    missing = [it for it in required if it.status == "missing"]
    rejected = [it for it in required if it.status == "rejected"]
    return {
        "required_total": len(required),
        "submitted_required": len(submitted),
        "missing_required": [{"key": it.key, "label": it.label} for it in missing],
        "rejected_required": [{"key": it.key, "label": it.label} for it in rejected],
        "is_complete": len(required) > 0 and not missing and not rejected,
    }


def _demo_milestones(profile: UserProfile) -> list[dict]:
    """MVP timeline: separates our material check from mock official status."""
    app = profile.application
    status = app.status_code if app else StatusCode.DRAFT
    completion = _material_completion_from_profile(profile) if app else {"is_complete": False}
    order = [
        ("profile", "Fill in profile"),
        ("documents", "Upload application materials"),
        ("completeness", "Material completeness check"),
        ("review", "Formal academic review"),
        ("decision", "Admission decision"),
    ]
    active_index = 0
    if app:
        active_index = 1 if not completion["is_complete"] else 2
        if status == StatusCode.UNDER_REVIEW:
            active_index = 3
        elif status in (StatusCode.OFFER, StatusCode.WAITLIST, StatusCode.REJECTED, StatusCode.ACCEPTED):
            active_index = 4
        elif status == StatusCode.DOCS_REQUIRED:
            active_index = 1
        elif status == StatusCode.SUBMITTED:
            active_index = 2
    out = []
    for idx, (key, label) in enumerate(order):
        state = "done" if idx < active_index else "current" if idx == active_index else "pending"
        out.append({"key": key, "label": label, "state": state})
    return out


def _escalation_packet(profile: UserProfile, next_step: str, outstanding_docs: list[dict]) -> dict:
    """Structured case summary for human hand-off in the MVP."""
    app = profile.application
    reason = "Supplement or verify application materials" if outstanding_docs else "Application status or policy issue requires human confirmation"
    return {
        "case_type": "admissions_support",
        "suggested_team": "NUS SoC MSc DFinTech Admissions / Programme Office",
        "reason": reason,
        "application_id": app.application_id if app else None,
        "current_status": app.status_code.value if app else "NO_APPLICATION",
        "outstanding_documents": outstanding_docs,
        "summary": next_step,
        "official_enquiry_url": "https://cloud.hello.nus.edu.sg/pg-enquiry?acquisition_source_id=B2C_WEBFORM_PG_SOC&programme_code=0300DFTCWK",
        "graduate_admission_system_url": "https://gradapp.nus.edu.sg/",
    }


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    if profile.application is None:
        return AgentResponse.needs(
            ["application"],
            "You have not submitted an application yet, so there is no trackable status for now.",
        )

    app = profile.application
    t = translate(app.status_code)
    today = date.fromisoformat(slots["today"]) if slots.get("today") else None

    timeline = build_timeline(app)
    eta_date = estimated_next_date(app.status_code, latest_status_date(app))
    reminders = build_reminders(profile, today=today)
    due = due_now(profile, today=today)  # preview only; does NOT write the log
    due_data = [
        {"kind": n.kind, "channels": n.channels, "date": n.date, "subject": n.subject,
         "message": n.message, "urgency": n.urgency, "reminder_keys": n.reminder_keys}
        for n in due
    ]

    # Link to #4: surface the specific docs blocking the application. Optional
    # supporting material is reported separately and never counted as blocking.
    outstanding_docs: list[dict] = []
    optional_docs: list[dict] = []
    next_step = t["next_step"]
    if app.status_code == StatusCode.DOCS_REQUIRED:
        outstanding_docs, optional_docs = _split_outstanding_documents(profile)
        if outstanding_docs:
            labels = _LABEL_SEPARATOR.join(d["label"] for d in outstanding_docs)
            next_step = (
                f"You still have {len(outstanding_docs)} required item(s) to handle: {labels}."
            )

    deadlines = [{"name": n, "date": d} for n, d in app.deadlines.items()]
    reminders_data = [
        {"key": r.key, "name": r.name, "date": r.date, "message": r.message,
         "urgency": r.urgency, "channels": r.channels}
        for r in reminders
    ]

    speakable = t["human_status"] + _SENTENCE_SEPARATOR + next_step
    if eta_date:
        speakable += f" (Expected progress by {eta_date})"
    if reminders:
        speakable += " Also: " + reminders[0].message

    return AgentResponse(
        status="ok",
        answer_type="official",  # status is sourced from the (mock) system
        speakable=speakable,
        data={
            "status_code": app.status_code.value,
            "human_status": t["human_status"],
            "next_step": next_step,
            "estimated_next_date": eta_date,
            "timeline": timeline,
            "outstanding_documents": outstanding_docs,
            "optional_documents": optional_docs,
            "deadlines": deadlines,
            "reminders": reminders_data,
            "possible_next_states": next_states(app.status_code),
            "material_completion": _material_completion_from_profile(profile),
            "demo_milestones": _demo_milestones(profile),
            "demo_disclaimer": "Demo / Mock Status: real official application status must come from the NUS Graduate Admission System. This system currently uses a mock admissions database.",
            "escalation_packet": _escalation_packet(profile, next_step, outstanding_docs),
            "due_now": due_data,
            "notification_prefs": _prefs_dict(profile),
        },
        sources=["application_system_mock"],
    )


def _prefs_dict(profile: UserProfile) -> dict:
    p = profile.notification_prefs
    return {
        "channels": [c.value for c in p.channels],
        "frequency": p.frequency.value,
        "muted_milestones": list(p.muted_milestones),
    }


def configure(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    """Update notification preferences (channels / frequency / per-milestone mute).

    Validates against the controlled vocabularies; invalid input returns
    need_clarification rather than silently dropping the change."""
    slots = slots or {}
    invalid: list[str] = []

    new_channels = profile.notification_prefs.channels
    if "channels" in slots:
        try:
            new_channels = [NotificationChannel(c) for c in slots["channels"]]
        except ValueError:
            invalid.append("channels")

    new_freq = profile.notification_prefs.frequency
    if "frequency" in slots:
        try:
            new_freq = NotificationFrequency(slots["frequency"])
        except ValueError:
            invalid.append("frequency")

    known = set(_MILESTONES.keys())
    mute = list(slots.get("mute", []))
    unmute = list(slots.get("unmute", []))
    if any(m not in known for m in (*mute, *unmute)):
        invalid.append("milestone")

    if invalid:
        return AgentResponse.needs(
            invalid,
            "Some notification settings are not recognised; please check and try again: " + ", ".join(invalid),
        )

    muted = [m for m in profile.notification_prefs.muted_milestones if m not in unmute]
    for m in mute:
        if m not in muted:
            muted.append(m)

    profile.notification_prefs.channels = new_channels
    profile.notification_prefs.frequency = new_freq
    profile.notification_prefs.muted_milestones = muted

    prefs = _prefs_dict(profile)
    speakable = (
        f"Notification settings updated: channels {', '.join(prefs['channels'])}; "
        f"frequency {prefs['frequency']}"
        + (f"; muted {', '.join(prefs['muted_milestones'])}" if prefs["muted_milestones"] else "")
        + "."
    )
    return AgentResponse(
        status="ok",
        answer_type="advisory",
        speakable=speakable,
        data={"notification_prefs": prefs},
    )
