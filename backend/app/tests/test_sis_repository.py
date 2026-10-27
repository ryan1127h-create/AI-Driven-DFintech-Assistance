"""domains/sis/repository.py: enrollment validation and upsert key,
self-reported-only deletes, and applications joined to their status
history and documents — against FakeDB, no database."""

from __future__ import annotations

import pytest

from app.domains.sis import repository
from app.tests.fake_db import FakeDB


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(repository, "sis_db", fake)
    return fake


def test_list_enrollments_optionally_filters_status(db):
    repository.list_enrollments("u1")
    repository.list_enrollments("u1", status="current")
    assert "and status" not in db.sql(0)
    assert "and status = %s" in db.sql(1)
    assert db.calls[1]["params"] == ["u1", "current"]


def test_list_enrollments_rejects_unknown_status(db):
    with pytest.raises(ValueError):
        repository.list_enrollments("u1", status="dropped")


def test_upsert_enrollment_keys_on_user_course_term(db):
    repository.upsert_enrollment("u1", "FT5005", term="AY2026/27 Sem1", status="completed", source="QA")
    assert "on conflict (user_id, course_code, term) do update" in db.sql(0)


@pytest.mark.parametrize("kwargs", [{"status": "dropped", "source": "QA"}, {"status": "current", "source": "CV"}])
def test_upsert_enrollment_rejects_unknown_enums(db, kwargs):
    with pytest.raises(ValueError):
        repository.upsert_enrollment("u1", "FT5005", term=None, **kwargs)
    assert db.calls == []


def test_delete_only_removes_self_reported_rows(db):
    assert repository.delete_self_reported_enrollment("u1", "e1") is False
    assert "and user_id = %s and source = 'QA'" in db.sql(0)


def test_list_applications_attaches_status_history(db):
    db.results = [
        [{"application_id": "a1", "status": "ACCEPTED"}, {"application_id": "a2", "status": "DRAFT"}],
        [
            {"application_id": "a1", "old_status": None, "new_status": "SUBMITTED"},
            {"application_id": "a1", "old_status": "SUBMITTED", "new_status": "ACCEPTED"},
        ],
    ]
    apps = repository.list_applications("u1")
    assert [h["new_status"] for h in apps[0]["status_history"]] == ["SUBMITTED", "ACCEPTED"]
    assert apps[1]["status_history"] == []
    assert db.calls[1]["params"] == [["a1", "a2"]]


def test_list_applications_skips_history_query_when_none(db):
    assert repository.list_applications("u1") == []
    assert len(db.calls) == 1
