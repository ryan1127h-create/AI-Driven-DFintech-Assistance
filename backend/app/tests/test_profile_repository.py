"""The profile-schema half of domains/profile/repository.py: every field
write updates field_values and appends its field_events row inside one
transaction (and rolls both back together), reads come from v_profile /
fields_for_purpose(), jsonb values are JSON-encoded, and bad enum inputs
are rejected before any SQL — against FakeDB, no database."""

from __future__ import annotations

import json

import pytest

from app.domains.profile import repository
from app.tests.fake_db import FakeDB


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(repository, "profile_db", fake)
    monkeypatch.setattr(repository, "_definitions", None)
    return fake


# --- set_field --------------------------------------------------------------

def test_set_field_writes_value_and_event_in_one_transaction(db):
    stored = {"field_key": "target_role_families", "value": ["data_analytics"]}
    db.results = [(["product_business"],), stored]

    row = repository.set_field(
        "u1", "target_role_families", ["data_analytics"], source="QA", actor="user:u1"
    )

    assert row == stored
    assert db.events == ["begin", "commit"]
    assert all(c["in_tx"] for c in db.calls)
    assert [c["method"] for c in db.calls] == ["fetch_one", "fetch_one_dict", "execute"]
    assert "for update" in db.sql(0)
    assert db.sql(1).startswith("insert into profile.field_values")
    assert json.loads(db.calls[1]["params"][2]) == ["data_analytics"]

    event = db.calls[2]
    assert event["sql"].startswith("insert into profile.field_events")
    user_id, field_key, action, old, new, source, actor = event["params"]
    assert (user_id, field_key, action, source, actor) == ("u1", "target_role_families", "set", "QA", "user:u1")
    assert json.loads(old) == ["product_business"]
    assert json.loads(new) == ["data_analytics"]


def test_set_field_on_a_new_field_records_null_old_value(db):
    db.results = [None, {"field_key": "code_level"}]
    repository.set_field("u1", "code_level", 2, source="CV", actor="agent:resume",
                         extraction="inferred", evidence_ref={"page": 1})
    params = db.calls[1]["params"]
    assert params[4] == "inferred"
    assert json.loads(params[6]) == {"page": 1}
    assert db.calls[2]["params"][3] is None


def test_set_field_rolls_back_value_when_event_insert_fails(monkeypatch):
    fake = FakeDB(results=[None, {}], fail_on="profile.field_events")
    monkeypatch.setattr(repository, "profile_db", fake)
    with pytest.raises(RuntimeError):
        repository.set_field("u1", "code_level", 2, source="QA", actor="user:u1")
    assert fake.events == ["begin", "rollback"]


@pytest.mark.parametrize("kwargs", [{"source": "SELF"}, {"source": "CV", "extraction": "guessed"}])
def test_set_field_rejects_unknown_enums_without_sql(db, kwargs):
    with pytest.raises(ValueError):
        repository.set_field("u1", "code_level", 2, actor="user:u1", **kwargs)
    assert db.calls == []


# --- confirm / delete -------------------------------------------------------

def test_confirm_field_without_a_stored_value_writes_no_event(db):
    assert repository.confirm_field("u1", "code_level", actor="user:u1") is False
    assert len(db.calls) == 1
    assert db.events == ["begin", "commit"]


def test_confirm_field_records_confirm_event(db):
    db.results = [(2, "CV")]
    assert repository.confirm_field("u1", "code_level", actor="user:u1") is True
    assert "set verified = true" in db.sql(0)
    assert db.calls[1]["params"][2] == "confirm"
    assert db.calls[1]["params"][5] == "CV"


def test_delete_field_records_old_value_and_null_new(db):
    db.results = [(["blockchain"], "QA")]
    assert repository.delete_field("u1", "target_role_families", actor="user:u1") is True
    _, _, action, old, new, source, _ = db.calls[1]["params"]
    assert (action, json.loads(old), new, source) == ("delete", ["blockchain"], None, "QA")


# --- reads ------------------------------------------------------------------

def test_get_profile_keys_rows_by_field(db):
    db.results = [[
        {"field_key": "study_mode", "value": "full_time", "source": "DB"},
        {"field_key": "code_level", "value": 2, "source": "QA"},
    ]]
    profile = repository.get_profile("u1")
    assert profile == {
        "study_mode": {"value": "full_time", "source": "DB"},
        "code_level": {"value": 2, "source": "QA"},
    }
    assert "from profile.v_profile where user_id = %s" in db.sql(0)


def test_get_profile_for_purpose_goes_through_consent_function(db):
    repository.get_profile_for_purpose("u1", "course")
    assert "from profile.fields_for_purpose(%s, %s)" in db.sql(0)
    assert db.calls[0]["params"] == ["u1", "course"]


def test_get_profile_for_purpose_rejects_unknown_purpose(db):
    with pytest.raises(ValueError):
        repository.get_profile_for_purpose("u1", "marketing")


def test_field_definitions_are_read_once(db):
    db.results = [[{"field_key": "code_level", "storage": "value"}]]
    first = repository.load_field_definitions()
    second = repository.load_field_definitions()
    assert first is second == {"code_level": {"field_key": "code_level", "storage": "value"}}
    assert len(db.calls) == 1


# --- conflicts, consents, derived ------------------------------------------

def test_record_conflict_validates_kind(db):
    with pytest.raises(ValueError):
        repository.record_conflict("u1", "code_level", kind="other", current_value=1,
                                   current_source="QA", candidate_value=3, candidate_source="CV")


def test_close_conflict_only_touches_open_rows(db):
    assert repository.close_conflict(7, "resolved") is False
    assert "where id = %s and status = 'open'" in db.sql(0)


def test_record_consent_appends_an_event(db):
    repository.record_consent("u1", "consent_cv_processing", True, notice_version="v1")
    assert db.sql(0).startswith("insert into profile.consent_events")
    assert db.calls[0]["params"] == ["u1", "consent_cv_processing", True, "{}", "v1"]


def test_save_derived_encodes_json_columns_and_defaults_flags(db):
    repository.save_derived("u1", {"profile_usability": "usable", "readiness_gap": {"code": 1}},
                            rules_version="r1")
    params = db.calls[0]["params"]
    cols = list(repository._DERIVED_COLUMNS)
    by_col = dict(zip(cols, params[1:1 + len(cols)]))
    assert by_col["profile_usability"] == "usable"
    assert json.loads(by_col["readiness_gap"]) == {"code": 1}
    assert json.loads(by_col["graduation_risk_flags"]) == []
    assert by_col["drop_off_risk"] is None
    assert params[-1] == "r1"
