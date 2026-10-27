"""checklist.service's application binding and the application shown on
the checklist — on in-memory stand-ins for sis, profile and auth."""

from __future__ import annotations

import pytest

from app.core.errors import ServiceUnavailableError, ValidationError
from app.domains.checklist import service


class _World:
    def __init__(self) -> None:
        self.stage = "prospect"
        self.email = "someone@gmail.com"
        # application_no -> {id, email, owner}
        self.applications = {"APP-1": {"id": "a1", "email": "Someone@Gmail.com", "owner": None}}
        self.stage_fails = False
        self.stage_calls: list[tuple] = []

    # sis
    def bind_application(self, user_id, application_no, email):
        app = self.applications.get(application_no)
        if app and app["owner"] is None and app["email"].lower() == email.lower():
            app["owner"] = user_id
            return app["id"]
        return None

    def unbind_application(self, user_id, application_id):
        for app in self.applications.values():
            if app["id"] == application_id and app["owner"] == user_id:
                app["owner"] = None
                return True
        return False

    def list_applications(self, user_id):
        return [
            {"application_no": no, "status": "SUBMITTED",
             "documents": [{"item_key": "referee_reports", "submitted": False},
                           {"item_key": "cv", "submitted": True},
                           {"item_key": "financial_support", "submitted": False}]}
            for no, app in self.applications.items() if app["owner"] == user_id
        ]

    # profile
    def get_profile_field(self, user_id, key):
        return self.stage

    def set_lifecycle_stage(self, user_id, stage, *, source, actor):
        self.stage_calls.append((stage, source, actor))
        if self.stage_fails:
            raise RuntimeError("profile store down")
        self.stage = stage


@pytest.fixture()
def world(monkeypatch):
    w = _World()
    for name in ("bind_application", "unbind_application", "list_applications"):
        monkeypatch.setattr(service.sis, name, getattr(w, name))
    monkeypatch.setattr(service.profile_interface, "get_profile_field", w.get_profile_field)
    monkeypatch.setattr(service.profile_interface, "set_lifecycle_stage", w.set_lifecycle_stage)
    monkeypatch.setattr(service.auth_interface, "get_login_email", lambda uid: w.email)
    monkeypatch.setattr(service.knowledge, "list_admissions_items", lambda: {
        "cv": {"label": "CV", "description": "Your CV.", "required": True},
        "referee_reports": {"label": "Referee Reports", "description": None, "required": True},
        "financial_support": {"label": "Financial Support", "description": None, "required": False},
    })
    monkeypatch.setattr(service.knowledge, "explain_application_status", lambda code: {
        "status_label": "Submitted" if code == "SUBMITTED" else None, "next_step": "Wait for review."})
    return w


def test_binding_moves_a_prospect_to_applicant(world):
    checklist = service.bind_application("u1", " APP-1 ")
    assert world.applications["APP-1"]["owner"] == "u1"
    assert world.stage_calls == [("applicant", "DB", "user:u1")]
    assert checklist.lifecycle_stage == "applicant"
    assert checklist.application.application_no == "APP-1"
    assert (checklist.application.status_label, checklist.application.next_step) == ("Submitted", "Wait for review.")
    # labelled from the admissions items, what's still missing first
    assert [(d.item_key, d.label, d.state) for d in checklist.application.documents] == [
        ("referee_reports", "Referee Reports", "missing"), ("cv", "CV", "received"),
        ("financial_support", "Financial Support", "optional")]


def test_a_different_login_email_cannot_bind(world):
    world.email = "someone-else@gmail.com"
    with pytest.raises(ValidationError, match="No unclaimed application"):
        service.bind_application("u1", "APP-1")
    assert world.applications["APP-1"]["owner"] is None
    assert world.stage_calls == []


def test_unknown_or_already_claimed_numbers_get_the_same_answer(world):
    with pytest.raises(ValidationError, match="No unclaimed application"):
        service.bind_application("u1", "APP-404")
    world.applications["APP-1"]["owner"] = "someone"
    with pytest.raises(ValidationError, match="No unclaimed application"):
        service.bind_application("u1", "APP-1")


def test_only_prospects_can_bind(world):
    world.stage = "current"
    with pytest.raises(ValidationError, match="only be bound"):
        service.bind_application("u1", "APP-1")
    assert world.applications["APP-1"]["owner"] is None


def test_a_failed_stage_update_undoes_the_binding(world):
    world.stage_fails = True
    with pytest.raises(ServiceUnavailableError):
        service.bind_application("u1", "APP-1")
    assert world.applications["APP-1"]["owner"] is None
    assert world.stage == "prospect"


def test_blank_number_is_rejected(world):
    with pytest.raises(ValidationError):
        service.bind_application("u1", "   ")
