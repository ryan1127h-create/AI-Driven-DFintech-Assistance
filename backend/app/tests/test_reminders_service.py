"""reminders.service: the reminders worked out from an applicant's records,
when they are urgent, how closing one works, and the dates the assistant is
given — on in-memory stand-ins for sis, the knowledge base, the programme
catalogue and the dismissals table."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domains.reminders import service

TODAY = date(2026, 10, 23)
ITEMS = {
    "transcript": {"label": "Official Transcript(s)", "required": True},
    "referee_reports": {"label": "Two Referee Reports", "required": True},
    "english_proficiency": {"label": "TOEFL / IELTS Score Report", "required": False},
    "cv": {"label": "CV", "required": True},
}


def _app(status, docs=None, **kw):
    return {"application_id": f"id-{status}", "application_no": f"DFT-{status}", "status": status,
            "documents": [{"item_key": k, "submitted": v} for k, v in (docs or {}).items()], **kw}


@pytest.fixture
def world(monkeypatch):
    state = {"apps": [], "closed": set(), "closes": date(2027, 1, 31)}
    monkeypatch.setattr(service.sis, "list_applications", lambda uid: state["apps"])
    monkeypatch.setattr(service.knowledge, "list_admissions_items", lambda: ITEMS)
    monkeypatch.setattr(service.program_catalog, "list_programs", lambda: [
        {"is_target": True, "deadlines": [{"closes_on": state["closes"]}]}, {"is_target": False, "deadlines": []}])
    monkeypatch.setattr(service.auth, "dismissed_reminder_keys", lambda uid: state["closed"])
    monkeypatch.setattr(service.auth, "dismiss_reminder", lambda uid, key: state["closed"].add(key))
    return state


def test_a_draft_is_reminded_with_the_closing_date_and_urgent_near_it(world):
    world["apps"] = [_app("DRAFT")]
    (reminder,) = service.list_reminders("u1", TODAY)
    assert reminder["kind"] == "draft" and reminder["urgent"] is False and reminder["due_date"] == "2027-01-31"
    assert "Submit it by 31 Jan 2027 (100 days left)" in reminder["body"]
    world["closes"] = date(2026, 11, 20)
    assert service.list_reminders("u1", TODAY)[0]["urgent"] is True


def test_missing_required_documents_only_until_the_school_asks_for_more(world):
    world["apps"] = [_app("UNDER_REVIEW", {"transcript": False, "english_proficiency": False, "cv": True})]
    (reminder,) = service.list_reminders("u1", TODAY)
    assert reminder["title"] == "1 document still missing for DFT-UNDER_REVIEW" and not reminder["urgent"]
    assert "TOEFL" not in reminder["body"]
    world["apps"] = [_app("DOCS_REQUIRED", {"transcript": False, "english_proficiency": False, "cv": True})]
    (reminder,) = service.list_reminders("u1", TODAY)
    assert reminder["urgent"] and "Review is paused" in reminder["body"] and "TOEFL" in reminder["body"]
    world["apps"] = [_app("SUBMITTED", {"english_proficiency": False, "cv": True})]
    assert service.list_reminders("u1", TODAY) == []  # only an optional item outstanding


def test_an_offer_deadline_until_it_passes(world):
    expires = datetime(2026, 11, 2, 15, 59, tzinfo=timezone.utc)  # 23:59 in Singapore
    world["apps"] = [_app("OFFER", {"cv": True, "english_proficiency": False}, offer_expires_at=expires)]
    (reminder,) = service.list_reminders("u1", TODAY)
    assert reminder["title"] == "Accept your offer by 2 Nov 2026" and "10 days left" in reminder["body"]
    assert reminder["action"]["prompt"] == "How do I accept my offer?" and not reminder["urgent"]
    assert service.list_reminders("u1", date(2026, 10, 30))[0]["urgent"]
    assert service.list_reminders("u1", date(2026, 11, 3)) == []


def test_closing_a_reminder_hides_only_that_situation(world):
    world["apps"] = [_app("DOCS_REQUIRED", {"transcript": False, "cv": True})]
    key = service.list_reminders("u1", TODAY)[0]["key"]
    service.dismiss("u1", key)
    assert service.list_reminders("u1", TODAY) == []
    world["apps"] = [_app("DOCS_REQUIRED", {"transcript": False, "cv": False})]  # another document now missing
    assert len(service.list_reminders("u1", TODAY)) == 1


def test_urgent_reminders_come_first(world):
    expires = datetime(2026, 10, 25, tzinfo=timezone.utc)
    world["apps"] = [_app("DRAFT"), _app("OFFER", offer_expires_at=expires)]
    assert [r["kind"] for r in service.list_reminders("u1", TODAY)] == ["offer_deadline", "draft"]


def test_the_assistant_gets_the_dates_whether_or_not_they_were_closed(world):
    expires = datetime(2026, 11, 2, 15, 59, tzinfo=timezone.utc)
    world["apps"] = [_app("OFFER", offer_expires_at=expires)]
    world["closed"].add(f"offer:id-OFFER:{date(2026, 11, 2)}")
    text = service.deadlines_text("u1", TODAY)
    assert "must be accepted by 2 November 2026 (10 days left)" in text
    world["apps"] = []
    assert service.deadlines_text("u1", TODAY) is None
