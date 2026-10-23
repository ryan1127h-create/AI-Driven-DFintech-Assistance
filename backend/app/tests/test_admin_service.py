"""Exercises domains/admin/service.py: every call requires an active admin,
account deletion and renaming go through the auth domain (so the Supabase
user goes too), and an administrator can't delete, demote or disable their
own account — on top of in-memory stand-ins for the auth interface and the
admin repository."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.domains.admin import service
from app.domains.admin.schemas import AdminUserUpdate

ADMIN = "admin-1"
STUDENT = "student-1"


class _FakeAuth:
    def __init__(self) -> None:
        self.admins = {ADMIN}
        self.deleted: list[str] = []
        self.renamed: list[tuple[str, str]] = []
        self.statuses: list[tuple[str, str]] = []

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.admins

    def delete_account(self, user_id: str) -> None:
        if user_id not in (ADMIN, STUDENT):
            raise NotFoundError("User not found.")
        self.deleted.append(user_id)

    def update_full_name(self, user_id: str, full_name: str) -> None:
        self.renamed.append((user_id, full_name))

    def set_account_status(self, user_id: str, status: str) -> None:
        self.statuses.append((user_id, status))


@pytest.fixture()
def auth(monkeypatch):
    fake = _FakeAuth()
    monkeypatch.setattr(service, "auth_interface", fake)
    return fake


@pytest.fixture()
def repo_updates(monkeypatch):
    updates: list[tuple[str, dict]] = []

    def update_user(user_id, changes):
        updates.append((user_id, dict(changes)))
        return {"user_id": user_id, **changes}

    monkeypatch.setattr(service.repository, "update_user", update_user)
    return updates


def test_non_admins_are_refused(auth, monkeypatch):
    monkeypatch.setattr(service.repository, "list_users", lambda search: pytest.fail("must not query"))
    with pytest.raises(ForbiddenError):
        service.list_users(STUDENT)


def test_deleting_a_user_deletes_through_auth(auth):
    assert service.delete_user(ADMIN, STUDENT) == {"status": "deleted", "user_id": STUDENT}
    assert auth.deleted == [STUDENT]


def test_deleting_a_missing_user_is_not_found(auth):
    with pytest.raises(NotFoundError):
        service.delete_user(ADMIN, "nobody")


def test_an_admin_cannot_delete_themself(auth):
    with pytest.raises(ValidationError):
        service.delete_user(ADMIN, ADMIN)
    assert auth.deleted == []


@pytest.mark.parametrize("changes", [{"role": "user"}, {"account_status": "disabled"}])
def test_an_admin_cannot_remove_their_own_access(auth, repo_updates, changes):
    with pytest.raises(ValidationError):
        service.update_user(ADMIN, ADMIN, changes)
    assert repo_updates == []


def test_an_admin_can_still_save_their_own_unchanged_access(auth, repo_updates):
    service.update_user(ADMIN, ADMIN, {"role": "admin", "account_status": "active"})
    assert auth.statuses == [(ADMIN, "active")]
    assert repo_updates == [(ADMIN, {"role": "admin"})]


def test_name_and_status_go_through_auth_and_the_role_through_the_repository(auth, repo_updates):
    service.update_user(ADMIN, STUDENT, {"full_name": "New Name", "account_status": "disabled", "role": "user"})
    assert auth.renamed == [(STUDENT, "New Name")]
    assert auth.statuses == [(STUDENT, "disabled")]
    assert repo_updates == [(STUDENT, {"role": "user"})]


@pytest.mark.parametrize("changes", [{"role": "owner"}, {"account_status": "banned"}])
def test_unknown_roles_and_statuses_are_rejected(auth, repo_updates, changes):
    with pytest.raises(ValidationError):
        service.update_user(ADMIN, STUDENT, changes)


def test_admin_names_are_trimmed_and_not_blank():
    assert AdminUserUpdate(full_name="  Jane   Tan ").full_name == "Jane Tan"
    with pytest.raises(PydanticValidationError):
        AdminUserUpdate(full_name="   ")


@pytest.fixture()
def app_updates(monkeypatch):
    calls: list[tuple[str, dict, str]] = []

    def update_application(application_id, changes, changed_by):
        calls.append((application_id, dict(changes), changed_by))
        return {"application_id": application_id, **changes}

    monkeypatch.setattr(service.repository, "update_application", update_application)
    return calls


def test_application_statuses_outside_the_constraint_are_rejected(auth, app_updates):
    with pytest.raises(ValidationError):
        service.update_application(ADMIN, "app-1", {"status": "PENDING"})
    assert app_updates == []


def test_application_updates_record_who_made_them_and_clear_blank_decisions(auth, app_updates):
    service.update_application(ADMIN, "app-1", {"status": "UNDER_REVIEW", "final_decision": "  "})
    assert app_updates == [("app-1", {"status": "UNDER_REVIEW", "final_decision": None}, ADMIN)]


class _FakeTx:
    def __init__(self, current_status):
        self.current_status = current_status
        self.statements: list[tuple[str, tuple]] = []

    def fetch_one_dict(self, query, params=()):
        return None if self.current_status is _MISSING else {"status": self.current_status}

    def execute(self, query, params=()):
        self.statements.append((" ".join(query.split()), tuple(params)))


_MISSING = object()


@pytest.fixture()
def fake_tx(monkeypatch):
    from contextlib import contextmanager

    from app.domains.admin import repository

    holder = {}

    @contextmanager
    def transaction():
        yield holder["tx"]

    monkeypatch.setattr(repository.reporting_db, "transaction", transaction)
    monkeypatch.setattr(repository, "get_application", lambda application_id: {"application_id": application_id})

    def use(current_status):
        holder["tx"] = _FakeTx(current_status)
        return holder["tx"]

    return use


def test_a_status_change_is_written_to_the_status_history(fake_tx):
    from app.domains.admin import repository

    tx = fake_tx("SUBMITTED")
    repository.update_application("app-1", {"status": "OFFER"}, ADMIN)
    assert [sql.split()[0] for sql, _ in tx.statements] == ["update", "insert"]
    assert tx.statements[1][1] == ("app-1", "SUBMITTED", "OFFER", ADMIN)


def test_an_unchanged_status_writes_no_history(fake_tx):
    from app.domains.admin import repository

    tx = fake_tx("OFFER")
    repository.update_application("app-1", {"status": "OFFER", "final_decision": "Admit"}, ADMIN)
    assert [sql.split()[0] for sql, _ in tx.statements] == ["update"]


def test_updating_a_missing_application_returns_none(fake_tx):
    from app.domains.admin import repository

    tx = fake_tx(_MISSING)
    assert repository.update_application("nope", {"status": "OFFER"}, ADMIN) is None
    assert tx.statements == []


@pytest.fixture()
def reloads(monkeypatch):
    """Fake knowledge interface (real chunk builders, fake embedding) and a
    fake chunk store; returns the list of reload_catalogue() calls."""
    from app.domains.knowledge_retrieval import chunk_builder

    calls: list[bool] = []

    class _FakeKnowledge:
        def __init__(self):
            self.chunk_builder = chunk_builder

        def reload_catalogue(self):
            calls.append(True)

        def embed_for_retrieval(self, text):
            return [0.1, 0.2]

    monkeypatch.setattr(service, "knowledge_interface", _FakeKnowledge())
    monkeypatch.setattr(service.repository, "fetch_chunk_source", lambda table, source_id: _SOURCES.get((table, source_id)))
    monkeypatch.setattr(service.repository, "store_chunk", lambda chunk, vector: True)
    return calls


_SOURCES = {
    ("courses", "FT5001"): {
        "row": {"course_code": "FT5001", "title": "New", "module_credit": 4, "department": "ISA", "status": "active",
                "annex_section": "Core Courses", "annex_intake": "2026", "description": "D.", "prerequisite": None,
                "preclusion": None},
        "tags": [], "previous_metadata": {"faculty": "Computing"},
    },
    ("admissions_items", "transcript"): {
        "row": {"key": "transcript", "label": "Transcript", "why": "W.", "required": True, "deadline_key": None},
        "tags": [], "previous_metadata": None,
    },
}


def test_key_only_course_relations_are_rejected_before_any_write(auth, reloads, monkeypatch):
    monkeypatch.setattr(service.repository, "update_knowledge_course_related", lambda *a: pytest.fail("must not write"))
    for relation in ("tags", "electives", "rules", "nonsense"):
        with pytest.raises(ValidationError):
            service.update_knowledge_course_related(ADMIN, "FT5001", relation, {"tag": "x"})
    assert reloads == []


def test_knowledge_edits_reload_the_cached_catalogue(auth, reloads, monkeypatch):
    monkeypatch.setattr(service.repository, "update_knowledge_course", lambda code, changes: {"course_code": code})
    monkeypatch.setattr(service.repository, "update_knowledge_course_related", lambda code, rel, row: {"course_code": code})
    monkeypatch.setattr(service.repository, "update_knowledge", lambda item, cat, changes: {"id": item})
    assert service.update_knowledge_course(ADMIN, "FT5001", {"title": "New"})["search_index"] == "updated"
    # Workload isn't part of the course's search text.
    assert service.update_knowledge_course_related(ADMIN, "FT5001", "workload", {"workload_lab": "2"})["search_index"] == "unchanged"
    assert service.update_knowledge_course_related(ADMIN, "FT5001", "description", {"description": "D."})["search_index"] == "updated"
    assert service.update_knowledge(ADMIN, "transcript", "admission_requirement", {"label": "Transcript"})["search_index"] == "updated"
    assert reloads == [True, True, True, True]


def test_an_edited_row_gets_its_chunk_rebuilt_and_re_embedded(auth, reloads, monkeypatch):
    stored = []
    monkeypatch.setattr(service.repository, "store_chunk", lambda chunk, vector: stored.append((chunk, vector)) or True)
    monkeypatch.setattr(service.repository, "update_knowledge", lambda item, cat, changes: {"id": item})
    service.update_knowledge(ADMIN, "transcript", "admission_requirement", {"label": "Transcript"})
    chunk, vector = stored[0]
    assert (chunk.chunk_key, chunk.source_table, vector) == ("admission:transcript", "admissions_items", [0.1, 0.2])
    assert chunk.content == "Transcript — Required. W."


def test_a_failed_re_embedding_keeps_the_edit_and_says_so(auth, reloads, monkeypatch):
    monkeypatch.setattr(service.repository, "update_knowledge", lambda item, cat, changes: {"id": item})

    def down(text):
        raise ConnectionError("openai down")

    monkeypatch.setattr(service.knowledge_interface, "embed_for_retrieval", down)
    result = service.update_knowledge(ADMIN, "transcript", "admission_requirement", {"label": "Transcript"})
    assert result == {"id": "transcript", "search_index": "failed"}
    assert reloads == [True]  # the catalogue is still reloaded: the row itself did change


def test_a_row_without_a_chunk_reports_missing(auth, reloads, monkeypatch):
    monkeypatch.setattr(service.repository, "update_knowledge", lambda item, cat, changes: {"id": item})
    monkeypatch.setattr(service.repository, "store_chunk", lambda chunk, vector: False)
    assert service.update_knowledge(ADMIN, "transcript", "admission_requirement", {})["search_index"] == "missing"
    assert service.update_knowledge(ADMIN, "SUBMITTED", "application_status", {})["search_index"] == "missing"


def test_a_failed_knowledge_edit_does_not_reload(auth, reloads, monkeypatch):
    monkeypatch.setattr(service.repository, "update_knowledge_course", lambda code, changes: None)
    with pytest.raises(NotFoundError):
        service.update_knowledge_course(ADMIN, "NOPE", {"title": "New"})
    assert reloads == []


def test_course_statuses_are_validated(auth, reloads):
    with pytest.raises(ValidationError):
        service.update_knowledge_course(ADMIN, "FT5001", {"status": "archived"})


def test_course_relation_updates_store_blank_fields_as_null(monkeypatch):
    from app.domains.admin import repository

    executed = []
    columns = ["course_code", "workload_lecture", "workload_lab", "workload_prep"]

    def fetch_all_dict(query, params=()):
        if "information_schema.columns" in query:
            return [{"column_name": c} for c in columns]
        return [{"column_name": "course_code", "constraint_type": "PRIMARY KEY"}]

    monkeypatch.setattr(repository.reporting_db, "fetch_all_dict", fetch_all_dict)
    monkeypatch.setattr(repository.reporting_db, "execute", lambda q, v: executed.append((" ".join(q.split()), list(v))))
    monkeypatch.setattr(repository, "get_knowledge_course", lambda code: {"course_code": code})
    repository.update_knowledge_course_related("FT5001", "workload", {"course_code": "FT5001", "workload_lab": "", "workload_prep": "3"})
    sql, values = executed[0]
    assert sql == "update knowledge.course_workload set workload_lab = %s, workload_prep = %s where course_code = %s"
    assert values == [None, "3", "FT5001"]


def test_reload_catalogue_drops_the_adapter_cache():
    from app.adapters.knowledge_db_adapter import KnowledgeDBAdapter

    loads = []
    adapter = KnowledgeDBAdapter(db=None)
    adapter._cached("courses", lambda: loads.append(1) or [])
    adapter._cached("courses", lambda: loads.append(1) or [])
    adapter.invalidate()
    adapter._cached("courses", lambda: loads.append(1) or [])
    assert loads == [1, 1]


def test_resolving_keeps_an_earlier_resolution(monkeypatch):
    from app.domains.admin import repository

    executed = []
    monkeypatch.setattr(repository.reporting_db, "execute", lambda q, p: executed.append((" ".join(q.split()), p)))
    monkeypatch.setattr(repository, "get_escalation", lambda case_id: {"id": case_id})
    repository.resolve_escalation("case-1", ADMIN, "Called the student back.")
    assert executed[0][0].endswith("where id = %s and status <> 'resolved'")
    assert "resolution_notes = %s" in executed[0][0]
    assert executed[0][1] == (ADMIN, "Called the student back.", "case-1")


def test_resolution_notes_are_trimmed_and_blank_ones_stored_as_null(auth, monkeypatch):
    calls = []
    monkeypatch.setattr(service.repository, "resolve_escalation", lambda case_id, by, notes: calls.append(notes) or {"id": case_id})
    service.resolve_escalation(ADMIN, "case-1", "  Refunded the fee.  ")
    service.resolve_escalation(ADMIN, "case-2", "   ")
    service.resolve_escalation(ADMIN, "case-3")
    assert calls == ["Refunded the fee.", None, None]


def test_resolution_notes_are_passed_through_over_http(client, auth, monkeypatch):
    from app.domains.auth.interface import get_current_user_id

    app, http = client
    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    seen = []
    monkeypatch.setattr(service, "resolve_escalation", lambda user_id, case_id, notes=None: seen.append(notes) or _CASE)
    http.patch("/api/v1/admin/escalations/case-1", json={"status": "Resolved", "resolution_notes": "Done"})
    assert seen == ["Done"]
    too_long = http.patch("/api/v1/admin/escalations/case-1", json={"status": "Resolved", "resolution_notes": "x" * 4001})
    assert too_long.status_code == 422


_CASE = {
    "id": "case-1", "shortId": "CASE", "name": "N", "initials": "N", "trigger": "Direct", "origin": "Admissions",
    "category": "Complaint", "priority": "Normal", "summary": "", "status": "Resolved",
    "createdDate": "—", "createdTime": "—",
}


def test_only_resolving_is_accepted_for_a_case():
    from app.domains.admin.schemas import AdminEscalationUpdate

    assert AdminEscalationUpdate(status="Resolved").status == "Resolved"
    with pytest.raises(PydanticValidationError):
        AdminEscalationUpdate(status="Open")


def test_escalation_rows_carry_an_iso_creation_time():
    from datetime import datetime, timezone

    from app.domains.admin import repository

    row = repository._escalation_row({
        "id": "a31f7c9b-44d2", "user_id": None, "full_name": "Sarah Tan", "email": "s@x.com",
        "trigger_source": "direct", "origin_specialist": "Admissions", "category": "policy_exception",
        "priority": "urgent", "summary": "", "status": "open",
        "created_at": datetime(2026, 10, 2, 8, 32, tzinfo=timezone.utc), "resolved_at": None, "resolved_by": None,
        "conversation_id": "aecf09b1-c10a", "resolution_notes": "Handled by phone.",
    })
    assert row["createdAt"] == "2026-10-02T08:32:00+00:00"
    assert (row["conversationId"], row["resolutionNotes"]) == ("aecf09b1-c10a", "Handled by phone.")
    assert (row["category"], row["priority"], row["initials"]) == ("Policy Exception", "Urgent", "ST")
    assert row["shortId"] == "A31F7C9B44D2"[-8:]


def test_short_case_ids_tell_apart_ids_sharing_a_prefix():
    from app.domains.admin import repository

    ids = ["6b2a2b9c-4b79-4db1-8d66-111111111111", "6b2a2b9c-4b79-4db1-8d66-222222222222"]
    assert [repository._short_case_id(i) for i in ids] == ["11111111", "22222222"]


# --- HTTP layer: every admin route is mounted, needs a token and an admin.

def _admin_routes():
    from app.domains.admin.api import router

    for route in router.routes:
        for method in route.methods:
            yield method, "/api/v1" + route.path.replace("{", "").replace("}", "")


@pytest.fixture()
def client():
    # Only the admin router on a bare app, not app.main: importing app.main
    # registers every tool, which changes how other test modules behave.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.router import router
    from app.core.errors import register_error_handlers

    app = FastAPI()
    app.include_router(router)
    register_error_handlers(app)
    return app, TestClient(app)


def test_admin_routes_require_a_token(client):
    _, http = client
    routes = list(_admin_routes())
    assert len(routes) == 26
    for method, path in routes:
        assert http.request(method, path, json={}).status_code in (401, 403), (method, path)


def test_admin_routes_refuse_non_admins(client, auth, monkeypatch):
    from app.domains.auth.interface import get_current_user_id

    app, http = client
    app.dependency_overrides[get_current_user_id] = lambda: STUDENT
    bodies = {
        ("PATCH", "/api/v1/admin/escalations/case_id"): {"status": "Resolved"},
        ("PATCH", "/api/v1/admin/checklist/item_id"): {"submitted": True},
        ("POST", "/api/v1/admin/alumni"): {"email": "a@x.com"},
    }
    for method, path in _admin_routes():
        response = http.request(method, path, json=bodies.get((method, path), {}))
        assert response.status_code == 403, (method, path, response.status_code)


def test_resolving_a_case_rejects_other_statuses_over_http(client, auth):
    from app.domains.auth.interface import get_current_user_id

    app, http = client
    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    assert http.patch("/api/v1/admin/escalations/case-1", json={"status": "Open"}).status_code == 422


def test_course_patches_reach_the_course_handler(client, auth, monkeypatch):
    from app.domains.auth.interface import get_current_user_id

    app, http = client
    app.dependency_overrides[get_current_user_id] = lambda: ADMIN
    monkeypatch.setattr(service, "update_knowledge", lambda *a: pytest.fail("generic knowledge handler hit"))
    monkeypatch.setattr(service, "update_knowledge_course", lambda user_id, code, changes: {"code": code, **changes})
    response = http.patch("/api/v1/admin/knowledge/courses/FT5001", json={"title": "New"})
    assert response.json() == {"code": "FT5001", "title": "New"}
