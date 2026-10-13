"""profile/service.py on an in-memory repository: the profile view (shown
fields, lock flags, expired tests), all-or-nothing validated edits,
lifecycle moves, conflicts, consents,
and the consent-filtered chat summary."""

from __future__ import annotations

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.domains.profile import interface, service
from app.tests.profile_fixtures import DEFINITIONS, ROLE_TAGS, entry


class _Repo:
    def __init__(self) -> None:
        self.profile: dict[str, dict] = {}
        self.purpose_fields: dict[str, set[str]] = {"adm": set(), "course": set(), "career": set()}
        self.conflicts: list[dict] = []
        self.consents: dict[str, dict] = {}
        self.writes: list[dict] = []
        self.set_calls: list[tuple] = []
        self.confirmed: list[str] = []
        self.closed: list[tuple] = []
        self.recorded_consents: list[tuple] = []
        self.derived: dict | None = None

    # reads
    def get_profile(self, user_id):
        return dict(self.profile)

    def get_profile_for_purpose(self, user_id, purpose):
        return {k: v for k, v in self.profile.items() if k in self.purpose_fields[purpose]}

    def get_field_value(self, user_id, key):
        e = self.profile.get(key)
        return {"field_key": key, **e} if e and e["source"] != "DB" else None

    def list_open_conflicts(self, user_id):
        return list(self.conflicts)

    def get_current_consents(self, user_id):
        return dict(self.consents)

    # writes
    def set_fields(self, user_id, changes, *, source, actor, from_cv=None):
        write = {"changes": changes, "source": source, "actor": actor}
        if from_cv:
            write["from_cv"] = from_cv
        self.writes.append(write)
        for k, v in changes.items():
            if v is None:
                self.profile.pop(k, None)
            else:
                self.profile[k] = entry(v, "CV" if k in (from_cv or {}) else source)

    def set_field(self, user_id, key, value, *, source, actor, verified=False, **_):
        self.set_calls.append((key, value, source, verified))
        self.profile[key] = entry(value, source, verified=verified)

    def confirm_field(self, user_id, key, *, actor):
        if key not in self.profile:
            return False
        self.confirmed.append(key)
        return True

    def close_conflict(self, conflict_id, status):
        self.closed.append((conflict_id, status))
        return True

    def record_consent(self, user_id, key, granted, *, notice_version, options=None):
        self.recorded_consents.append((key, granted, notice_version))


@pytest.fixture()
def repo(monkeypatch):
    fake = _Repo()
    r = service.repository
    monkeypatch.setattr(r, "load_field_definitions", lambda: DEFINITIONS)
    monkeypatch.setattr(r, "list_cv_quotes", lambda user_id: {})
    monkeypatch.setattr(r, "get_derived", lambda user_id: fake.derived)
    monkeypatch.setattr(r, "has_consent", lambda user_id, key: bool(fake.consents.get(key, {}).get("granted")))
    monkeypatch.setattr(service, "_role_tags", lambda: ROLE_TAGS)
    for name in ("get_profile", "get_profile_for_purpose", "get_field_value", "list_open_conflicts",
                 "get_current_consents", "set_fields", "set_field", "confirm_field", "close_conflict",
                 "record_consent"):
        monkeypatch.setattr(r, name, getattr(fake, name))
    return fake


# --- view -------------------------------------------------------------------

def test_profile_view_shows_displayed_fields_with_lock_flags(repo):
    repo.profile = {
        "lifecycle_stage": entry("prospect"),
        "code_level": entry(2, "CV"),
        "study_mode": entry("full_time", "DB"),
        "academic_standing": entry("good", "DB"),   # hidden
        "admission_tests": entry([{"key": "IELTS", "score": 7, "test_date": "2020-01-01"}, {"key": "GRE", "score": 320}]),
    }
    view = service.get_profile("u1")
    assert set(view["fields"]) == {"lifecycle_stage", "code_level", "study_mode", "admission_tests"}
    assert view["fields"]["code_level"]["editable"] is True
    assert view["fields"]["lifecycle_stage"]["editable"] is False
    assert view["fields"]["study_mode"]["locked_reason"] == "from school records"
    assert view["fields"]["admission_tests"]["value"] == [{"key": "GRE", "score": 320}]
    assert view["open_conflicts"] == 0


def test_definitions_hide_internal_fields(repo):
    defs = service.get_definitions()
    keys = {d["field_key"] for d in defs["fields"]}
    assert "drop_off_risk" not in keys and "motivation_segment" not in keys and "language_pref" not in keys
    by_key = {d["field_key"]: d for d in defs["fields"]}
    assert by_key["code_level"]["editable"] and not by_key["lifecycle_stage"]["editable"]
    assert defs["role_tags"] == ROLE_TAGS


# --- edits ------------------------------------------------------------------

def test_update_fields_validates_and_writes_in_one_batch(repo):
    view = service.update_fields("u1", {"code_level": "3", "target_role_families": ["blockchain"], "certifications": None})
    assert repo.writes == [{
        "changes": {"code_level": 3, "target_role_families": ["blockchain"], "certifications": None},
        "source": "QA", "actor": "user:u1",
    }]
    assert view["fields"]["code_level"]["value"] == 3


def test_update_fields_is_all_or_nothing(repo):
    repo.profile = {"study_mode": entry("full_time", "DB")}
    with pytest.raises(ValidationError) as exc:
        service.update_fields("u1", {
            "code_level": 2,
            "code_level_typo": 1,
            "lifecycle_stage": "current",
            "study_mode": "part_time",
            "target_markets": ["MARS"],
            "drop_off_risk": "low",
        })
    message = str(exc.value)
    for fragment in ("code_level_typo: unknown", "lifecycle_stage: read-only", "study_mode: read-only",
                     "target_markets:", "drop_off_risk: unknown"):
        assert fragment in message
    assert repo.writes == []


def test_update_fields_requires_something(repo):
    with pytest.raises(ValidationError):
        service.update_fields("u1", {})


def test_stage_change(repo):
    repo.profile = {"lifecycle_stage": entry("prospect")}
    service.set_lifecycle_stage("u1", "applicant", source="DB", actor="user:u1")
    assert repo.writes[-1] == {"changes": {"lifecycle_stage": "applicant"}, "source": "DB", "actor": "user:u1"}


def test_first_stage_and_unchanged_stage(repo):
    service.set_lifecycle_stage("u1", "prospect", source="QA", actor="user:u1")
    assert repo.writes[-1]["changes"] == {"lifecycle_stage": "prospect"}
    service.set_lifecycle_stage("u1", "prospect", source="QA", actor="user:u1")
    assert len(repo.writes) == 1  # no-op


# --- conflicts --------------------------------------------------------------

def _conflict(**kw):
    return {"id": 7, "field_key": "code_level", "kind": "self_vs_cv", "current_value": 1,
            "current_source": "QA", "candidate_value": 3, "candidate_source": "CV", "created_at": None, **kw}


def test_accepting_a_conflict_candidate(repo):
    repo.conflicts = [_conflict()]
    service.resolve_conflict("u1", 7, "accept_candidate")
    assert repo.set_calls == [("code_level", 3, "CV", True)]
    assert repo.closed == [(7, "resolved")]


def test_keeping_current_and_dismissing(repo):
    repo.profile = {"code_level": entry(1)}
    repo.conflicts = [_conflict()]
    service.resolve_conflict("u1", 7, "keep_current")
    assert repo.confirmed == ["code_level"] and repo.closed == [(7, "resolved")]
    service.resolve_conflict("u1", 7, "dismiss")
    assert repo.closed[-1] == (7, "dismissed")
    assert repo.set_calls == []


def test_conflicts_must_be_the_users_own_and_open(repo):
    with pytest.raises(NotFoundError):
        service.resolve_conflict("u1", 99, "dismiss")
    with pytest.raises(ValidationError):
        service.resolve_conflict("u1", 7, "ignore")


# --- consents ---------------------------------------------------------------

def test_consents_default_to_not_granted(repo):
    repo.consents = {"consent_system_data": {"granted": True, "created_at": None}}
    consents = {c["key"]: c["granted"] for c in service.get_consents("u1")}
    assert consents == {
        "consent_personalized_rec": False, "consent_system_data": True, "consent_cv_processing": False,
        "consent_alumni_matching": False, "consent_model_improvement": False,
    }


def test_update_consents_records_only_changes(repo):
    repo.consents = {"consent_system_data": {"granted": True, "created_at": None}}
    service.update_consents("u1", {"consent_system_data": True, "consent_personalized_rec": True})
    assert repo.recorded_consents == [("consent_personalized_rec", True, service.NOTICE_VERSION)]
    with pytest.raises(ValidationError):
        service.update_consents("u1", {"consent_everything": True})


# --- chat summary -----------------------------------------------------------

def test_summary_without_consent_only_has_the_stage(repo):
    repo.profile = {"lifecycle_stage": entry("prospect"), "code_level": entry(2)}
    assert service.chat_summary_text("u1").splitlines()[1:] == ["- Lifecycle stage (lifecycle_stage): prospect"]


def test_summary_with_consent(repo):
    repo.profile = {
        "lifecycle_stage": entry("current"),
        "code_level": entry(2),
        "target_role_families": entry(["blockchain"]),
        "current_modules": entry([{"course_code": "FT5005", "term": "AY2026/27 Sem1"}, {"course_code": "FT5002"}], "DB"),
        "application_record": entry([{"application_no": "A1", "status": "ACCEPTED", "missing_items": ["cv", "transcript"]}], "DB"),
    }
    repo.purpose_fields["course"] = {"code_level", "current_modules"}
    repo.purpose_fields["adm"] = {"application_record"}
    repo.purpose_fields["career"] = {"target_role_families"}
    assert service.chat_summary_text("u1").splitlines()[1:] == [
        "- Lifecycle stage (lifecycle_stage): current",
        "- Programming proficiency (code_level): Has written data-processing scripts independently (2)",
        "- Target role families (target_role_families): Blockchain (blockchain)",
        "- Application record (application_record): A1: ACCEPTED, 2 document(s) not yet received",
        "- Current courses (current_modules): FT5005, FT5002",
    ]


def test_summary_is_empty_without_a_profile(repo):
    assert service.chat_summary_text("u1") == ""


def test_interface_reads_one_field(repo):
    repo.profile = {"lifecycle_stage": entry("prospect")}
    assert interface.get_profile_field("u1", "lifecycle_stage") == "prospect"
    assert interface.get_profile_field("u1", "code_level") is None


def test_summary_adds_derived_course_notes_only_with_consent(repo):
    repo.profile = {"lifecycle_stage": entry("current")}
    repo.derived = {
        "readiness_gap": {"maths_stats": {"level": 1, "required": 2, "gap": 1, "status": "gap", "evidence": []},
                          "finance": {"level": None, "required": 1, "gap": None, "status": "unknown", "evidence": []}},
        "graduation_risk_flags": [{"code": "overload", "message": "28 units this semester is a heavy load."}],
    }
    assert "derived" not in service.chat_summary_text("u1")

    repo.consents = {"consent_personalized_rec": {"granted": True}}
    summary = service.chat_summary_text("u1")
    assert "maths and statistics self-rated at level 1, below the level 2" in summary
    assert "Graduation risk (derived): 28 units this semester is a heavy load." in summary
    assert "finance" not in summary



def test_readiness_gaps_for_career_planning_need_the_consent(repo):
    repo.derived = {"readiness_gap": {
        "maths_stats": {"level": 1, "required": 2, "gap": 1, "status": "gap", "evidence": []},
        "programming": {"level": 3, "required": 2, "gap": 0, "status": "met", "evidence": []},
    }}
    assert interface.derived_readiness_gaps("u1") == []
    repo.consents = {"consent_personalized_rec": {"granted": True}}
    assert interface.derived_readiness_gaps("u1") == [{"area": "maths_stats", "level": 1, "required": 2}]
