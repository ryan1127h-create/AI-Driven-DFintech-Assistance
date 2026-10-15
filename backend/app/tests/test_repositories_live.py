"""The account/profile/sis repositories against the live database — the
things FakeDB can't show: that the SQL actually runs against the current
schema, that the field_values trigger rejects bad values, that v_profile
folds sis facts in, and that fields_for_purpose() honours consents.

Skipped unless RUN_LIVE_DB_TESTS=1. Every repository call is routed into
one transaction opened with force_rollback, so nothing a test writes is
ever committed. The adapter tests at the bottom are the exception: they
check commit/rollback visibility from a second connection, using a
throwaway chat.conversations row they delete again.

    RUN_LIVE_DB_TESTS=1 pytest app/tests/test_repositories_live.py
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import psycopg
import pytest

from app.adapters.postgres_pool import PostgresPool, SchemaDB, _Session
from app.core.config import settings
from app.core.errors import ValidationError
from app.domains.auth import repository as account_repo
from app.domains.checklist import service as checklist_service
from app.domains.knowledge_retrieval import interface as knowledge
from app.domains.profile import repository as profile_repo
from app.domains.profile import service as profile_service
from app.domains.profile.validation import is_displayed, lock_reason, validate_value
from app.domains.sis import repository as sis_repo

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)


def _connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, autocommit=True, prepare_threshold=None, connect_timeout=5)


class _RollbackDB:
    """RelationalDBPort over one connection that is inside a
    force_rollback transaction; transaction() nests as a savepoint."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._session = _Session(conn)

    def __getattr__(self, name):
        return getattr(self._session, name)

    @contextmanager
    def transaction(self):
        with self._conn.transaction():
            yield self._session


@pytest.fixture()
def db(monkeypatch):
    conn = _connect()
    try:
        with conn.transaction(force_rollback=True):
            fake = _RollbackDB(conn)
            for repo, name in ((account_repo, "account_db"), (profile_repo, "profile_db"), (sis_repo, "sis_db")):
                monkeypatch.setattr(repo, name, fake)
            monkeypatch.setattr(profile_repo, "_definitions", None)
            yield fake
    finally:
        conn.close()


@pytest.fixture()
def user_id(db) -> str:
    """A user with an academic record, so v_profile has sis facts."""
    row = db.fetch_one("select user_id from sis.academic_records order by user_id limit 1")
    if row is None:
        pytest.skip("no user with an academic record")
    return str(row[0])


# --- account ----------------------------------------------------------------

def test_account_and_settings_roundtrip(db, user_id):
    account = account_repo.get_account(user_id)
    assert account["role"] in account_repo.ROLES
    assert account_repo.get_account_by_email(account["email"])["user_id"] == account["user_id"]

    updated = account_repo.update_settings(user_id, {"answer_depth": "detailed", "language_pref": ["zh", "en"]})
    assert updated["answer_depth"] == "detailed"
    assert updated["language_pref"] == ["zh", "en"]
    assert account_repo.set_role(str(uuid.uuid4()), "admin") is False


# --- profile ----------------------------------------------------------------

def test_set_field_is_readable_and_logged(db, user_id):
    before = profile_repo.get_field_value(user_id, "target_role_families")
    profile_repo.set_field(user_id, "target_role_families", ["data_analytics", "risk_management"],
                           source="QA", actor="test:live")

    assert profile_repo.get_profile(user_id)["target_role_families"]["value"] == ["data_analytics", "risk_management"]
    event = profile_repo.list_field_events(user_id, "target_role_families", limit=1)[0]
    assert (event["action"], event["actor"]) == ("set", "test:live")
    assert event["old_value"] == (before["value"] if before else None)

    assert profile_repo.confirm_field(user_id, "target_role_families", actor="test:live") is True
    assert profile_repo.get_field_value(user_id, "target_role_families")["verified"] is True
    assert profile_repo.delete_field(user_id, "target_role_families", actor="test:live") is True
    assert "target_role_families" not in profile_repo.get_profile(user_id)


def test_trigger_rejects_values_outside_the_dictionary(db, user_id):
    with pytest.raises(psycopg.errors.RaiseException, match="not a knowledge tag"):
        profile_repo.set_field(user_id, "target_role_families", ["astrology"], source="QA", actor="test:live")
    with pytest.raises(psycopg.errors.RaiseException, match="not an allowed value"):
        profile_repo.set_field(user_id, "code_level", 9, source="QA", actor="test:live")
    with pytest.raises(psycopg.errors.RaiseException, match="stored in sis"):
        profile_repo.set_field(user_id, "track_chosen", "undecided", source="QA", actor="test:live")


def test_v_profile_includes_sis_facts(db, user_id):
    profile = profile_repo.get_profile(user_id)
    record = sis_repo.get_academic_record(user_id)
    assert profile["study_mode"] == {**profile["study_mode"], "value": record["study_mode"], "source": "DB"}


def test_fields_for_purpose_follows_consent(db, user_id):
    defs = profile_repo.load_field_definitions()
    assert len(defs) == 77

    profile_repo.record_consent(user_id, "consent_personalized_rec", False, notice_version="test")
    assert profile_repo.get_profile_for_purpose(user_id, "course") == {}

    for key in ("consent_personalized_rec", "consent_system_data", "consent_cv_processing"):
        profile_repo.record_consent(user_id, key, True, notice_version="test")
    assert profile_repo.has_consent(user_id, "consent_system_data") is True

    expected = {
        k for k in profile_repo.get_profile(user_id)
        if k in defs and defs[k]["user_visible"] and "course" in defs[k]["purpose_tags"]
    }
    assert expected, "no course-purpose facts on this user; the test would prove nothing"
    assert set(profile_repo.get_profile_for_purpose(user_id, "course")) == expected


def test_conflict_derived_and_cv_roundtrip(db, user_id):
    conflict_id = profile_repo.record_conflict(
        user_id, "code_level", kind="self_vs_cv", current_value=1, current_source="QA",
        candidate_value=3, candidate_source="CV",
    )
    assert [c["id"] for c in profile_repo.list_open_conflicts(user_id)][-1] == conflict_id
    assert profile_repo.close_conflict(conflict_id, "dismissed") is True
    assert profile_repo.close_conflict(conflict_id, "resolved") is False

    profile_repo.save_derived(user_id, {"profile_usability": "usable", "readiness_gap": {"code": 1}},
                              rules_version="test")
    derived = profile_repo.get_derived(user_id)
    assert (derived["profile_usability"], derived["readiness_gap"], derived["graduation_risk_flags"]) == (
        "usable", {"code": 1}, [])

    doc = profile_repo.create_cv_document(user_id, storage_bucket="b", storage_path="p")
    assert profile_repo.set_cv_parse_status(doc["id"], "parsed") is True
    assert profile_repo.mark_cv_purged(doc["id"]) is True
    latest = profile_repo.get_latest_cv_document(user_id)
    assert (latest["parse_status"], latest["storage_path"]) == ("parsed", None)


# --- sis --------------------------------------------------------------------

def test_self_reported_enrollment_roundtrip(db, user_id):
    enrolled = {e["course_code"] for e in sis_repo.list_enrollments(user_id)}
    course = db.fetch_one(
        "select course_code from knowledge.courses where not (course_code = any(%s)) order by course_code limit 1",
        (list(enrolled),),
    )[0]

    row = sis_repo.upsert_enrollment(user_id, course, term=None, status="completed", source="QA")
    again = sis_repo.upsert_enrollment(user_id, course, term=None, status="completed", source="QA", grade_band="A")
    assert again["id"] == row["id"]
    assert course in {e["course_code"] for e in sis_repo.list_enrollments(user_id, status="completed")}

    registry_row = next(e for e in sis_repo.list_enrollments(user_id) if e["source"] == "DB")
    assert sis_repo.delete_self_reported_enrollment(user_id, registry_row["id"]) is False
    assert sis_repo.delete_self_reported_enrollment(user_id, row["id"]) is True


def test_applications_and_program(db, user_id):
    items = knowledge.list_admissions_items()
    for app in sis_repo.list_applications(user_id):
        assert isinstance(app["status_history"], list)
        for doc in app["documents"]:
            # sis returns keys only; every key is an admissions item the
            # checklist can label
            assert set(doc) == {"item_key", "submitted"} and doc["item_key"] in items
    assert sis_repo.get_program("DFT")["total_credit_required"] == 52


# --- CV data ---------------------------------------------------------------

def test_cv_data_can_be_forgotten_while_values_stay(db, user_id):
    doc = profile_repo.create_cv_document(user_id, storage_bucket=None, storage_path=None)
    quote = "BSc Computer Science, 2021"
    profile_repo.save_cv_result(str(doc["id"]), candidates={"highest_degree": {"value": "bachelor", "quote": quote}})
    profile_repo.set_fields(user_id, {"highest_degree": "bachelor"}, source="QA", actor="test:live",
                            from_cv={"highest_degree": {"cv_document_id": str(doc["id"]), "quote": quote}})
    assert profile_repo.list_cv_quotes(user_id)["highest_degree"] == quote

    assert profile_repo.delete_cv_data(user_id) >= 1
    assert profile_repo.get_cv_document(user_id, str(doc["id"]))["candidates"] == {}
    assert "highest_degree" not in profile_repo.list_cv_quotes(user_id)
    assert profile_repo.get_profile(user_id)["highest_degree"]["value"] == "bachelor"


# --- adapter: commit / rollback as seen from another connection --------------

@pytest.fixture()
def adapter():
    own_pool = PostgresPool(settings.database_url, max_size=2)
    yield SchemaDB("chat", own_pool)
    own_pool.close()


def _exists_elsewhere(conversation_id: str) -> bool:
    with _connect() as other:
        return other.execute(
            "select 1 from chat.conversations where conversation_id = %s", (conversation_id,)
        ).fetchone() is not None


def test_adapter_transaction_commits_and_rolls_back(adapter):
    committed, rolled_back = str(uuid.uuid4()), str(uuid.uuid4())
    insert = "insert into chat.conversations (conversation_id) values (%s)"
    try:
        with adapter.transaction() as tx:
            tx.execute(insert, (committed,))
        assert _exists_elsewhere(committed)

        with pytest.raises(RuntimeError):
            with adapter.transaction() as tx:
                tx.execute(insert, (rolled_back,))
                raise RuntimeError("abort")
        assert not _exists_elsewhere(rolled_back)

        adapter.execute("update chat.conversations set turn_count = 1 where conversation_id = %s", (committed,))
        with _connect() as other:
            assert other.execute(
                "select turn_count from chat.conversations where conversation_id = %s", (committed,)
            ).fetchone()[0] == 1
    finally:
        adapter.execute("delete from chat.conversations where conversation_id = any(%s)",
                        ([committed, rolled_back],))
    assert not _exists_elsewhere(committed)


# --- profile service / validation against the live dictionary and trigger ---

def _sample(key: str, d: dict, tags: list[str]):
    """One valid value per editable field, built from its definition."""
    allowed = d["allowed_values"]
    if key == "admission_tests":
        return [{"key": "GRE", "score": 325, "test_date": "2025-03-01"}]
    if key == "current_position":
        return {"role_family": tags[0], "region": "SG", "seniority": "junior"}
    if key == "currently_hiring":
        return {"hiring": True, "role_families": tags[:1]}
    if key == "languages":
        return [{"key": "en", "level": "fluent"}]
    vt = d["value_type"]
    if vt == "bool":
        return True
    if vt == "year":
        return 2020
    if vt == "term":
        return "AY2027/28 Sem1"
    if vt == "single":
        return allowed[0] if allowed else tags[0]
    if vt == "multi":
        return [allowed[0]] if allowed else (tags[:2] if d["values_ref"] else ["NTU MSc FinTech"])
    raise AssertionError(f"no sample for {key} ({vt})")


def test_every_editable_field_passes_validation_and_the_trigger(db):
    user = str(db.fetch_one("select user_id from account.accounts order by created_at limit 1")[0])
    defs = profile_repo.load_field_definitions()
    tags = sorted(profile_service._role_tags())
    editable = {k: d for k, d in defs.items() if is_displayed(d) and lock_reason(d, None) is None}
    assert len(editable) == 49  # the 51 field_values fields minus lifecycle_stage and sub_stage
    values = {k: validate_value(k, _sample(k, d, tags), defs, set(tags)) for k, d in editable.items()}
    profile_repo.set_fields(user, values, source="QA", actor="test:live")
    stored = {k: profile_repo.get_field_value(user, k)["value"] for k in values}
    assert stored == values


@pytest.fixture()
def prospect(db) -> tuple[str, str]:
    """(user_id, email) of an account turned into a prospect without an
    application, inside the rolled-back transaction."""
    user, email = db.fetch_one("select user_id, email from account.accounts order by created_at limit 1")
    user = str(user)
    db.execute("update sis.applications set user_id = null where user_id = %s", (user,))
    profile_repo.set_fields(user, {"lifecycle_stage": "prospect"}, source="QA", actor="test:live")
    return user, email


def test_profile_update_and_stage_change(db, prospect):
    user, _ = prospect
    view = profile_service.update_fields(user, {"target_role_families": ["blockchain"], "code_level": "2"})
    assert view["fields"]["code_level"]["value"] == 2
    with pytest.raises(ValidationError):
        profile_service.update_fields(user, {"lifecycle_stage": "current"})

    profile_service.set_lifecycle_stage(user, "applicant", source="DB", actor="test:live")
    after = profile_repo.get_profile(user)
    assert after["lifecycle_stage"]["value"] == "applicant"
    assert after["target_role_families"]["value"] == ["blockchain"]


def test_binding_an_application_end_to_end(db, prospect):
    user, email = prospect
    db.execute(
        """
        insert into sis.applications (application_id, program_id, application_no, application_type,
               admission_term, submission_date, status, applicant_email)
        select gen_random_uuid(), program_id, 'LIVE-TEST-0001', 'coursework', 'AY2027/28 Sem1', now(),
               'SUBMITTED', upper(%s)
          from sis.programs limit 1
        """,
        (email,),
    )
    with pytest.raises(ValidationError):
        checklist_service.bind_application(user, "LIVE-TEST-9999")

    checklist = checklist_service.bind_application(user, "LIVE-TEST-0001")
    assert checklist.lifecycle_stage == "applicant"
    assert checklist.application.application_no == "LIVE-TEST-0001"
    assert checklist.application.status == "SUBMITTED"
    # v_profile now shows the application's status as the sub-stage
    assert profile_repo.get_profile(user)["sub_stage"]["value"] == "SUBMITTED"
    with pytest.raises(ValidationError):
        checklist_service.bind_application(user, "LIVE-TEST-0001")



# --- conversation store against chat.conversations -----------------------------

def test_conversation_state_roundtrip_keeps_declined_fields_and_contexts(db, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage

    from app.domains.conversation import repository as conversation_repo
    from app.domains.conversation.models import ConversationState

    monkeypatch.setattr(conversation_repo, "chat_db", db)
    store = conversation_repo.SupabaseConversationStore()
    session_id = str(uuid.uuid4())
    context = {"tool": "career", "mode": "exploration", "subjects": ["data_analytics"], "awaiting": None}
    store.save_state(session_id, ConversationState(
        turn_count=1, raw_tail=[HumanMessage("q"), AIMessage("a")],
        pending_turn_intents=[{"turn": 1, "intents": ["career"], "agent_used": "career_agent",
                               "contexts": [context]}],
        declined_fields=["job_search_timeline"],
    ))
    loaded = store.get_state(session_id)
    assert loaded.declined_fields == ["job_search_timeline"]
    assert loaded.pending_turn_intents[0]["contexts"] == [context]
