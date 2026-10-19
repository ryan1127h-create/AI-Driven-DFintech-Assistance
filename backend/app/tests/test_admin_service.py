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

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.admins

    def delete_account(self, user_id: str) -> None:
        if user_id not in (ADMIN, STUDENT):
            raise NotFoundError("User not found.")
        self.deleted.append(user_id)

    def update_full_name(self, user_id: str, full_name: str) -> None:
        self.renamed.append((user_id, full_name))


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
    assert repo_updates == [(ADMIN, {"role": "admin", "account_status": "active"})]


def test_renaming_goes_through_auth_and_the_rest_through_the_repository(auth, repo_updates):
    service.update_user(ADMIN, STUDENT, {"full_name": "New Name", "account_status": "disabled"})
    assert auth.renamed == [(STUDENT, "New Name")]
    assert repo_updates == [(STUDENT, {"account_status": "disabled"})]


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
    calls: list[bool] = []

    class _FakeKnowledge:
        def reload_catalogue(self):
            calls.append(True)

    monkeypatch.setattr(service, "knowledge_interface", _FakeKnowledge())
    return calls


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
    service.update_knowledge_course(ADMIN, "FT5001", {"title": "New"})
    service.update_knowledge_course_related(ADMIN, "FT5001", "workload", {"workload_lab": "2"})
    service.update_knowledge(ADMIN, "transcript", "admission_requirement", {"label": "Transcript"})
    assert reloads == [True, True, True]


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
    repository.resolve_escalation("case-1", ADMIN)
    assert executed[0][0].endswith("where id = %s and status <> 'resolved'")
    assert executed[0][1] == (ADMIN, "case-1")


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
    })
    assert row["createdAt"] == "2026-10-02T08:32:00+00:00"
    assert (row["category"], row["priority"], row["initials"]) == ("Policy Exception", "Urgent", "ST")


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
    assert len(routes) == 20
    for method, path in routes:
        assert http.request(method, path, json={}).status_code in (401, 403), (method, path)


def test_admin_routes_refuse_non_admins(client, auth, monkeypatch):
    from app.domains.auth.interface import get_current_user_id

    app, http = client
    app.dependency_overrides[get_current_user_id] = lambda: STUDENT
    bodies = {"/api/v1/admin/escalations/case_id": {"status": "Resolved"}, "/api/v1/admin/checklist/item_id": {"submitted": True}}
    for method, path in _admin_routes():
        response = http.request(method, path, json=bodies.get(path, {}))
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
