"""Exercises domains/alumni/service.py — who may use Alumni Match, ranking
by role interests, what each side can see before and after a request is
accepted, the consent and limits on sending, the request state machine, and
the staff directory rules — on top of in-memory stand-ins for the alumni
repository and the auth, profile and knowledge interfaces."""

from __future__ import annotations

import itertools
from datetime import datetime, timezone

import pytest

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domains.alumni import service

TAGS = ["blockchain", "data_analytics", "machine_learning_ai", "risk_management"]
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


class _Repo:
    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.requests: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def list_profiles(self, listed_only=False):
        return [dict(p) for p in self.profiles.values() if p["listed"] or not listed_only]

    def get_profile(self, user_id):
        p = self.profiles.get(user_id)
        return dict(p) if p else None

    def insert_profile(self, user_id, fields):
        self.profiles[user_id] = {
            "user_id": user_id, "class_year": None, "expertise": [], "bio": None, "photo_url": None,
            "contact_email": None, "contact_phone": None, "linkedin_url": None, "listed": False, **fields,
        }
        return {"user_id": user_id}

    def update_profile(self, user_id, fields):
        if user_id not in self.profiles:
            return False
        self.profiles[user_id].update(fields)
        return True

    def delete_profile(self, user_id):
        return self.profiles.pop(user_id, None) is not None

    def requests_for_student(self, student_id):
        return [dict(r) for r in self.requests.values() if r["student_id"] == student_id]

    def requests_for_alumnus(self, alumni_id):
        return [dict(r) for r in self.requests.values() if r["alumni_id"] == alumni_id and r["status"] != "cancelled"]

    def get_request(self, request_id):
        r = self.requests.get(request_id)
        return dict(r) if r else None

    def count_pending_sent(self, student_id):
        return sum(1 for r in self.requests.values() if r["student_id"] == student_id and r["status"] == "pending")

    def insert_request(self, student_id, alumni_id, note):
        if any(r["student_id"] == student_id and r["alumni_id"] == alumni_id and r["status"] in ("pending", "accepted")
               for r in self.requests.values()):
            return None
        rid = f"r{next(self._ids)}"
        self.requests[rid] = {"id": rid, "student_id": student_id, "alumni_id": alumni_id, "note": note,
                              "status": "pending", "shared_contact": {}, "reply_note": None,
                              "created_at": NOW, "responded_at": None}
        return dict(self.requests[rid])

    def set_request_status(self, request_id, from_status, to_status, shared_contact=None, reply_note=None):
        r = self.requests.get(request_id)
        if r is None or r["status"] != from_status:
            return None
        r["status"] = to_status
        if shared_contact is not None:
            r["shared_contact"] = shared_contact
        r["reply_note"] = reply_note
        if to_status in ("accepted", "declined"):
            r["responded_at"] = NOW
        return dict(r)


class _World:
    """Accounts, profile stages/interests/consents and the role tags."""

    def __init__(self):
        self.accounts = {
            "alice": {"full_name": "Alice Tan", "email": "alice@alumni.com"},
            "bob": {"full_name": "Bob Lee", "email": "bob@alumni.com"},
            "carol": {"full_name": "Carol Ng", "email": "carol@alumni.com"},
            "sam": {"full_name": "Sam Student", "email": "sam@u.nus.edu"},
            "pat": {"full_name": "Pat Applicant", "email": "pat@gmail.com"},
        }
        self.stages = {"alice": "alumni", "bob": "alumni", "carol": "alumni", "sam": "current", "pat": "applicant"}
        self.interests = {"sam": {"target_role_families": ["data_analytics", "machine_learning_ai"], "main_target_role": "machine_learning_ai"}}
        self.consents = {("sam", "consent_alumni_matching")}
        self.stage_changes: list[tuple] = []
        self.purposes_read: list[tuple] = []
        # What sam's profile releases for purpose "alumni".
        self.shared = {"sam": {
            "target_role_families": ["data_analytics", "machine_learning_ai", "risk_management"],
            "main_target_role": "machine_learning_ai", "graduation_term": "2026-12",
            "total_work_years": "1-3", "target_markets": ["SG", "HK"], "mentor_seeking": True,
        }}


@pytest.fixture()
def world(monkeypatch):
    repo, w = _Repo(), _World()
    monkeypatch.setattr(service, "repository", repo)

    class _Auth:
        def get_account_names(self, ids):
            return {i: w.accounts[i] for i in ids if i in w.accounts}

        def find_user_id_by_email(self, email):
            return next((i for i, a in w.accounts.items() if a["email"] == email.strip().lower()), None)

    class _Profile:
        def get_profile_field(self, user_id, key):
            return w.stages.get(user_id) if key == "lifecycle_stage" else None

        def get_profile_for_purpose(self, user_id, purpose):
            w.purposes_read.append((user_id, purpose))
            if purpose == "alumni":
                # The real fields_for_purpose: nothing without the matching consent.
                return w.shared.get(user_id, {}) if (user_id, "consent_alumni_matching") in w.consents else {}
            return w.interests.get(user_id, {})

        def has_consent(self, user_id, key):
            return (user_id, key) in w.consents

        def field_labels(self, keys):
            return {k: k.replace("_", " ").capitalize() for k in keys}

        def describe_value(self, key, value):
            return ", ".join(value) if isinstance(value, list) else str(value)

        def set_lifecycle_stage(self, user_id, stage, *, source, actor):
            w.stage_changes.append((user_id, stage, source, actor))
            w.stages[user_id] = stage

    class _Knowledge:
        def list_role_tags(self):
            return [{"tag": t, "name_en": t.replace("_", " ").title()} for t in TAGS]

    monkeypatch.setattr(service, "auth_interface", _Auth())
    monkeypatch.setattr(service, "profile_interface", _Profile())
    monkeypatch.setattr(service, "knowledge_interface", _Knowledge())
    for uid, tags, listed in [("alice", ["machine_learning_ai", "data_analytics"], True),
                              ("bob", ["blockchain"], True), ("carol", ["data_analytics"], False)]:
        repo.insert_profile(uid, {"position": "Engineer", "company": "Acme", "expertise": tags, "listed": listed,
                                  "contact_email": f"{uid}@work.com", "linkedin_url": f"https://linkedin.com/in/{uid}"})
    w.repo = repo
    return w


def test_only_enrolled_students_and_alumni_get_in(world):
    assert service.viewer_kind("sam") == "student"
    assert service.viewer_kind("alice") == "alumni"
    with pytest.raises(ForbiddenError):
        service.viewer_kind("pat")
    with pytest.raises(ForbiddenError):
        service.list_matches("alice")  # alumni don't browse alumni


def test_matches_rank_listed_alumni_by_the_students_interests(world):
    result = service.list_matches("sam")
    assert [m["id"] for m in result["items"]] == ["alice", "bob"]  # carol is unlisted
    alice = result["items"][0]
    assert alice["score"] == 3 and alice["matched"] == ["Machine Learning Ai", "Data Analytics"]
    assert result["ranked_by_interests"] is True and result["can_send_requests"] is True


def test_matches_never_carry_contact_details(world):
    for item in service.list_matches("sam")["items"]:
        assert not {"contact_email", "contact_phone", "linkedin_url", "email"} & set(item)


def test_matches_filter_by_search_and_expertise(world):
    assert [m["id"] for m in service.list_matches("sam", search="bob")["items"]] == ["bob"]
    assert [m["id"] for m in service.list_matches("sam", expertise=["blockchain"])["items"]] == ["bob"]


def test_without_interests_the_list_is_alphabetical(world):
    world.interests.clear()
    result = service.list_matches("sam")
    assert [m["name"] for m in result["items"]] == ["Alice Tan", "Bob Lee"] and result["ranked_by_interests"] is False


def test_sending_needs_the_matching_consent(world):
    world.consents.clear()
    assert service.list_matches("sam")["can_send_requests"] is False
    with pytest.raises(ValidationError, match="privacy settings"):
        service.send_request("sam", "alice", "Hi")


def test_unlisted_or_unknown_alumni_cannot_be_contacted(world):
    for alumni_id in ("carol", "nobody"):
        with pytest.raises(NotFoundError):
            service.send_request("sam", alumni_id, None)


def test_one_open_request_per_alumnus_and_a_pending_cap(world, monkeypatch):
    service.send_request("sam", "alice", "  Hi Alice  ")
    assert world.repo.requests["r1"]["note"] == "Hi Alice"
    with pytest.raises(ConflictError):
        service.send_request("sam", "alice", None)
    monkeypatch.setattr(service, "MAX_PENDING_SENT", 1)
    with pytest.raises(ValidationError, match="at most 1"):
        service.send_request("sam", "bob", None)


def test_contact_details_appear_only_after_acceptance_and_only_those_shared(world):
    request = service.send_request("sam", "alice", "Hi")
    sent = service.list_requests("sam")["sent"][0]
    assert sent["contact"] is None and sent["alumnus"]["name"] == "Alice Tan"
    incoming = service.list_requests("alice")["incoming"][0]
    assert incoming["student"]["email"] is None and incoming["student"]["stage"] == "Current student"

    service.respond("alice", request["id"], "accept", ["email"], "Happy to help")
    sent = service.list_requests("sam")["sent"][0]
    assert sent["contact"] == {"email": "alice@work.com"} and sent["reply_note"] == "Happy to help"
    assert service.list_requests("alice")["incoming"][0]["student"]["email"] == "sam@u.nus.edu"


def test_an_alumnus_sees_why_the_student_matches_and_their_background(world):
    service.send_request("sam", "alice", None)
    student = service.list_requests("alice")["incoming"][0]["student"]
    # alice's expertise: machine_learning_ai, data_analytics.
    assert student["match"] == {
        "shared": ["Machine Learning Ai", "Data Analytics"], "main_role": "Machine Learning Ai",
        "main_role_shared": True, "other": ["Risk Management"],
    }
    assert student["background"] == [
        {"label": "Graduation term", "value": "2026-12"},
        {"label": "Total work years", "value": "1-3"},
        {"label": "Target markets", "value": "SG, HK"},
    ]
    assert student["mentor_seeking"] is True
    # Read only through the "alumni" purpose, which the consent gates.
    assert ("sam", "alumni") in world.purposes_read


def test_without_the_consent_an_alumnus_sees_no_profile_details(world):
    service.send_request("sam", "bob", None)
    world.consents.clear()  # withdrawn after sending
    student = service.list_requests("bob")["incoming"][0]["student"]
    assert student["match"] == {"shared": [], "main_role": None, "main_role_shared": False, "other": []}
    assert student["background"] == [] and student["mentor_seeking"] is False


def test_an_alumnus_cannot_share_what_their_entry_lacks(world):
    request = service.send_request("sam", "alice", None)
    with pytest.raises(ValidationError, match="no phone"):
        service.respond("alice", request["id"], "accept", ["phone"], None)


def test_answered_requests_stay_answered(world):
    request = service.send_request("sam", "alice", None)
    service.respond("alice", request["id"], "decline", [], None)
    with pytest.raises(ConflictError):
        service.respond("alice", request["id"], "accept", ["email"], None)
    with pytest.raises(ConflictError):
        service.cancel_request("sam", request["id"])
    # After a decline the student may ask again.
    assert service.send_request("sam", "alice", "Second try")["status"] == "pending"


def test_only_the_parties_can_act_on_a_request(world):
    request = service.send_request("sam", "alice", None)
    with pytest.raises(NotFoundError):
        service.respond("bob", request["id"], "accept", [], None)
    with pytest.raises(ForbiddenError):
        service.respond("sam", request["id"], "accept", [], None)
    with pytest.raises(NotFoundError):
        service.cancel_request("alice", request["id"])
    assert service.cancel_request("sam", request["id"])["status"] == "cancelled"
    assert service.list_requests("alice")["incoming"] == []


def test_alumni_list_themselves_but_staff_cannot(world):
    assert service.set_listed("carol", True)["listed"] is True
    with pytest.raises(ValidationError, match="Only the alumnus"):
        service.staff_update("bob", {"listed": True})
    assert service.staff_update("bob", {"listed": False})["listed"] is False


def test_staff_create_makes_an_unlisted_alumnus(world):
    world.stages["sam"] = "graduating"
    created = service.staff_create("admin-1", " SAM@u.nus.edu ", {"position": "Analyst", "company": "Bank",
                                                                  "expertise": ["risk_management"], "listed": True})
    assert created["listed"] is False and created["email"] == "sam@u.nus.edu"
    assert world.stage_changes == [("sam", "alumni", "DB", "admin:admin-1")]
    with pytest.raises(ConflictError):
        service.staff_create("admin-1", "sam@u.nus.edu", {"position": "A", "company": "B"})


def test_staff_create_checks_its_input(world):
    with pytest.raises(NotFoundError):
        service.staff_create("admin-1", "nobody@x.com", {"position": "A", "company": "B"})
    with pytest.raises(ValidationError, match="required"):
        service.staff_create("admin-1", "pat@gmail.com", {"position": "A"})
    with pytest.raises(ValidationError, match="Unknown expertise"):
        service.staff_create("admin-1", "pat@gmail.com", {"position": "A", "company": "B", "expertise": ["cooking"]})
    assert "pat" not in world.repo.profiles


def test_a_failed_stage_change_leaves_no_directory_entry(world, monkeypatch):
    def down(*a, **k):
        raise RuntimeError("profile down")

    monkeypatch.setattr(service.profile_interface, "set_lifecycle_stage", down)
    with pytest.raises(RuntimeError):
        service.staff_create("admin-1", "pat@gmail.com", {"position": "A", "company": "B"})
    assert "pat" not in world.repo.profiles


def test_alumni_routes_refuse_applicants_over_http(world):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.router import router
    from app.core.errors import register_error_handlers
    from app.domains.auth.interface import get_current_user_id

    app = FastAPI()
    app.include_router(router)
    register_error_handlers(app)
    app.dependency_overrides[get_current_user_id] = lambda: "pat"
    http = TestClient(app)
    assert http.get("/api/v1/alumni/matches").status_code == 403
    assert http.get("/api/v1/alumni/requests").status_code == 403
    assert http.post("/api/v1/alumni/requests", json={"alumni_id": "alice"}).status_code == 403
    app.dependency_overrides[get_current_user_id] = lambda: "sam"
    assert http.get("/api/v1/alumni/matches?expertise=blockchain").json()["total"] == 1
    assert http.patch("/api/v1/alumni/requests/r9", json={"action": "approve"}).status_code == 422


# --- story sharing -----------------------------------------------------------------

def test_alumni_choose_who_sees_their_story_and_staff_can_only_withdraw(world):
    mine = service.set_visibility("alice", {"story_for_applicants": True})
    assert mine["story_for_applicants"] is True and mine["story_for_students"] is False and mine["listed"] is True
    with pytest.raises(ValidationError, match="Nothing to change"):
        service.set_visibility("alice", {"photo_url": "x"})
    with pytest.raises(ValidationError, match="share their story"):
        service.staff_update("alice", {"story_for_students": True})
    service.staff_update("alice", {"story_for_applicants": False})
    assert world.repo.profiles["alice"]["story_for_applicants"] is False


def test_stories_come_only_from_consenting_alumni_matching_the_readers_goals(world):
    world.repo.profiles["alice"].update(story_for_applicants=True, bio="From ML research into fintech.", class_year=2023)
    world.repo.profiles["carol"].update(story_for_applicants=True, class_year=2024)  # unlisted still shares a story
    world.repo.profiles["bob"].update(story_for_students=True)
    found = service.stories("applicants", ["data_analytics", "machine_learning_ai"])
    assert [s["name"].split()[0] for s in found] == ["Alice", "Carol"]  # alice covers both, carol the main role
    assert found[0]["bio"] == "From ML research into fintech." and "contact_email" not in found[0]
    assert service.stories("applicants", ["blockchain"]) == []  # bob shares with students only
    assert [s["name"].split()[0] for s in service.stories("students", ["blockchain"])] == ["Bob"]
    assert service.stories("applicants", []) == []
