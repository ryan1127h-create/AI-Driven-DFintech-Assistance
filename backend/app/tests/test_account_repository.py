"""The account-schema half of domains/auth/repository.py: which tables and
columns each function touches, input validation before any SQL runs, and
the "no such account" return values — against FakeDB, no database."""

from __future__ import annotations

import pytest

from app.domains.auth import repository
from app.tests.fake_db import FakeDB


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(repository, "account_db", fake)
    return fake


def test_get_account_reads_account_accounts_by_id(db):
    db.results = [{"user_id": "u1", "role": "user"}]
    assert repository.get_account("u1") == {"user_id": "u1", "role": "user"}
    assert "from account.accounts where user_id = %s" in db.sql(0)
    assert db.calls[0]["params"] == ["u1"]


def test_get_account_by_email_filters_on_email(db):
    repository.get_account_by_email("a@u.nus.edu")
    assert "where email = %s" in db.sql(0)


def test_touch_last_login_updates_account_accounts(db):
    repository.touch_last_login("u1")
    assert db.sql(0).startswith("update account.accounts set last_login_at = now()")


def test_set_role_rejects_unknown_role_without_sql(db):
    with pytest.raises(ValueError):
        repository.set_role("u1", "applicant")
    assert db.calls == []


def test_set_role_reports_missing_account(db):
    assert repository.set_role("u1", "admin") is False
    db.results = [("u1",)]
    assert repository.set_role("u1", "admin") is True


def test_set_status_rejects_unknown_status(db):
    with pytest.raises(ValueError):
        repository.set_status("u1", "banned")


def test_update_settings_ignores_unknown_keys(db):
    db.results = [{"answer_depth": "concise"}]
    repository.update_settings("u1", {"answer_depth": "concise", "role": "admin"})
    sql = db.sql(0)
    assert sql.startswith("update account.user_settings set answer_depth = %s, updated_at = now()")
    assert "role" not in sql.split("returning")[0]
    assert db.calls[0]["params"] == ["concise", "u1"]


def test_update_settings_rejects_bad_answer_depth(db):
    with pytest.raises(ValueError):
        repository.update_settings("u1", {"answer_depth": "verbose"})
    assert db.calls == []


def test_update_settings_with_nothing_to_change_just_reads(db):
    repository.update_settings("u1", {"unknown": 1})
    assert len(db.calls) == 1
    assert db.sql(0).startswith("select language_pref, answer_depth, email_notifications")


def test_onboarding_status_rejects_unknown_values(db):
    with pytest.raises(ValueError):
        repository.set_onboarding_status("u1", "half_done")
    assert db.calls == []


def test_onboarding_status_is_read_from_user_settings(db):
    db.results = [{"onboarding_status": "skipped"}]
    assert repository.get_onboarding_status("u1") == "skipped"
    assert "from account.user_settings where user_id = %s" in db.sql(0)
