"""Derived labels: each rule on small inputs, the service gathering its
inputs and storing the result (on in-memory stand-ins), and the event hook
that triggers recomputation."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core import events
from app.domains.derived_labels import rules
from app.domains.derived_labels import service as derived

TODAY = date(2026, 10, 3)


def _def(key, tier="P0", stages=("PRO",), sources=("QA",), storage="value"):
    return {"field_key": key, "tier": tier, "stages": list(stages), "sources": list(sources),
            "storage": storage, "user_visible": True}


DEFINITIONS = {d["field_key"]: d for d in [
    _def("lifecycle_stage"),
    _def("program_motivation"),
    _def("career_goal_clarity"),
    _def("target_role_families"),
    _def("main_target_role"),
    _def("highest_degree", sources=("CV",)),
    _def("completed_modules", stages=("PRO",), sources=("DB",), storage="sis"),  # school records: never required
    _def("gpa_band", tier="P1"),
    _def("languages", tier="P1"),
]}

COMPLETE = {
    "lifecycle_stage": "prospect", "program_motivation": "switch", "career_goal_clarity": "clear",
    "target_role_families": ["data_analytics"], "highest_degree": "bachelor",
}


# --- profile_usability / motivation_segment ---------------------------------------

def test_usability_needs_every_answerable_p0_field():
    assert rules.profile_usability(COMPLETE, DEFINITIONS, "PRO") == "usable"
    assert rules.profile_usability({**COMPLETE, "gpa_band": "unknown", "languages": [{"key": "en"}]}, DEFINITIONS, "PRO") == "rich"
    assert rules.profile_usability({**COMPLETE, "highest_degree": None}, DEFINITIONS, "PRO") == "not_ready"


def test_usability_applies_tier_conditions():
    # Several role families make the main role required; exploring makes neither required.
    assert rules.profile_usability({**COMPLETE, "target_role_families": ["a", "b"]}, DEFINITIONS, "PRO") == "not_ready"
    exploring = {**COMPLETE, "career_goal_clarity": "exploring", "target_role_families": None}
    assert rules.profile_usability(exploring, DEFINITIONS, "PRO") == "usable"


def test_motivation_is_stated_or_cautiously_inferred():
    assert rules.motivation_segment({"program_motivation": "found"}) == "found"
    assert rules.motivation_segment({"total_work_years": "0", "employment_status": "student"}) == "launch"
    assert rules.motivation_segment({"career_goal_clarity": "exploring"}) == "explore"
    assert rules.motivation_segment({"total_work_years": "3-5"}) is None


def test_usability_needs_a_motivation_before_graduating():
    no_motivation = {**COMPLETE, "program_motivation": None}
    definitions = {k: d for k, d in DEFINITIONS.items() if k != "program_motivation"}
    assert rules.profile_usability(no_motivation, definitions, "PRO") == "not_ready"
    grd = {k: {**d, "stages": ["GRD"]} for k, d in definitions.items()}
    assert rules.profile_usability(no_motivation, grd, "GRD") == "usable"


# --- readiness_gap ----------------------------------------------------------------------

def test_readiness_uses_ratings_then_evidence_and_never_guesses_a_gap():
    gaps = rules.readiness_gap({
        "code_level": 1, "math_stats_level": 3,
        "degree_discipline_category": "finance_econ_accounting", "prior_coursework": ["accounting"],
    })
    assert (gaps["programming"]["status"], gaps["programming"]["gap"]) == ("gap", 1)
    assert gaps["maths_stats"]["status"] == "met"
    assert gaps["finance"]["status"] == "likely_met"
    assert gaps["finance"]["evidence"] == ["degree: finance_econ_accounting", "coursework: accounting"]
    assert rules.readiness_gap({})["finance"]["status"] == "unknown"


# --- drop_off_risk ------------------------------------------------------------------------

def _application(status, days_ago, missing=("cv",)):
    changed = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time(), tzinfo=timezone.utc)
    return {
        "status": status,
        "status_history": [{"old_status": "SUBMITTED", "new_status": status, "changed_at": changed}],
        "documents": [{"item_key": k, "submitted": False} for k in missing] + [{"item_key": "photo", "submitted": True}],
    }


def test_drop_off_risk():
    required = {"cv", "photo"}
    assert rules.drop_off_risk(None, required, {}, TODAY) is None
    assert rules.drop_off_risk(_application("DOCS_REQUIRED", 20), required, {}, TODAY) == "high"
    assert rules.drop_off_risk(_application("DOCS_REQUIRED", 3), required, {}, TODAY) == "mid"
    assert rules.drop_off_risk(_application("DRAFT", 45, missing=()), required, {}, TODAY) == "high"
    assert rules.drop_off_risk(_application("UNDER_REVIEW", 3, missing=()), required, {}, TODAY) == "low"
    worried = {"concerns": [{"key": "visa", "note": "processing time"}]}
    assert rules.drop_off_risk(_application("UNDER_REVIEW", 3, missing=()), required, worried, TODAY) == "mid"
    comparing = {"competing_programs": ["NTU MSc FinTech", "SMU MITB"]}
    assert rules.drop_off_risk(_application("UNDER_REVIEW", 3, missing=()), required, comparing, TODAY) == "mid"
    # An optional document missing is not a warning sign.
    assert rules.drop_off_risk(_application("UNDER_REVIEW", 3, missing=("referee",)), required, {}, TODAY) == "low"


# --- graduation_risk_flags ------------------------------------------------------------------

def _progress(remaining=(), level4000=0):
    return {"core_mandatory_remaining": list(remaining), "elective_level4000_used": level4000}


def _flags(values, **overrides):
    kwargs = dict(
        completed_progress=_progress(), projected_progress=_progress(), planned_progress=_progress(),
        current_units=16.0, current_codes=set(), planned_codes=set(), today=TODAY,
    )
    kwargs.update(overrides)
    return [f["code"] for f in rules.graduation_risk_flags(values, **kwargs)]


def test_terms_map_to_consecutive_semesters():
    assert rules.semester_index("AY2026/27 Sem2") - rules.semester_index("AY2026/27 Sem1") == 1
    assert rules.semester_index("AY2027/28 Sem1") - rules.semester_index("AY2026/27 Sem2") == 1
    assert rules.current_semester_index(TODAY) == rules.semester_index("AY2026/27 Sem1")
    assert rules.current_semester_index(date(2027, 2, 1)) == rules.semester_index("AY2026/27 Sem2")
    assert rules.semester_index("2027 spring") is None


def test_no_flags_for_a_student_on_track():
    assert _flags({"gpa_current_band": ">=3.0", "academic_standing": "good", "expected_grad_term": "AY2027/28 Sem1"}) == []


def test_each_graduation_risk():
    assert _flags({"gpa_current_band": "<3.0"}) == ["gpa_below_requirement"]
    assert _flags({"academic_standing": "probation"}) == ["gpa_below_requirement"]
    # Next semester is the last one and core is still outstanding after this one.
    assert _flags({"expected_grad_term": "AY2026/27 Sem2"}, projected_progress=_progress(["BMD5302"])) == ["core_behind"]
    assert _flags({"expected_grad_term": "AY2027/28 Sem2"}, projected_progress=_progress(["BMD5302"])) == []
    assert _flags({}, planned_progress=_progress(level4000=3)) == ["level4000_over_limit"]
    assert _flags({}, planned_codes={"FT5007"}, completed_progress=_progress(["IT5006"])) == ["capstone_prerequisites"]
    assert _flags({"study_mode": "part_time"}, current_units=16.0) == ["overload"]
    assert _flags({"study_mode": "full_time", "weekly_study_hours": "<10"}, current_units=16.0) == ["overload"]
    assert _flags({"study_mode": "full_time"}, current_units=24.0) == []


# --- service --------------------------------------------------------------------------------

@pytest.fixture()
def world(monkeypatch):
    stored = {}
    state = {
        "values": {**COMPLETE, "lifecycle_stage": "current", "gpa_current_band": "<3.0", "code_level": 1},
        "enrollments": [{"course_code": "BMD5301", "status": "current", "credits": 4}],
    }
    p = derived.profile_interface
    monkeypatch.setattr(p, "get_profile_values", lambda uid: state["values"])
    monkeypatch.setattr(p, "field_definitions", lambda: DEFINITIONS)
    monkeypatch.setattr(p, "save_derived_labels", lambda uid, labels, version: stored.update(uid=uid, labels=labels, version=version))
    monkeypatch.setattr(p, "get_derived_labels", lambda uid: stored.get("row"))
    monkeypatch.setattr(derived.sis, "list_enrollments", lambda uid: state["enrollments"])
    monkeypatch.setattr(derived.sis, "list_applications", lambda uid: [])
    monkeypatch.setattr(derived.knowledge, "list_courses", lambda: [{"course_code": "BMD5301", "module_credit": 4}])
    monkeypatch.setattr(derived.knowledge, "list_course_electives", lambda: {})
    monkeypatch.setattr(derived.knowledge, "list_admissions_items", lambda: {})
    return state, stored


def test_recompute_stores_stage_appropriate_labels(world):
    state, stored = world
    labels = derived.recompute("u1")
    assert stored["version"] == rules.RULES_VERSION and stored["labels"] == labels
    assert labels["motivation_segment"] == "switch"
    assert labels["readiness_gap"]["programming"]["status"] == "gap"
    assert labels["drop_off_risk"] is None  # applicants only
    assert [f["code"] for f in labels["graduation_risk_flags"]] == ["gpa_below_requirement"]

    state["values"] = {**COMPLETE, "lifecycle_stage": "alumni"}
    labels = derived.recompute("u1")
    assert labels["readiness_gap"] is None and labels["graduation_risk_flags"] == []


def test_returning_users_are_recomputed_only_when_stale(world, monkeypatch):
    _, stored = world
    calls = []
    monkeypatch.setattr(derived, "recompute", calls.append)
    fresh = datetime.now(timezone.utc)
    stored["row"] = {"rules_version": rules.RULES_VERSION, "computed_at": fresh}
    derived.refresh_if_stale("u1")
    stored["row"] = {"rules_version": rules.RULES_VERSION, "computed_at": fresh - timedelta(days=1)}
    derived.refresh_if_stale("u1")
    stored["row"] = {"rules_version": "2025-01", "computed_at": fresh}
    derived.refresh_if_stale("u1")
    assert calls == ["u1", "u1"]


def test_events_run_handlers_off_the_request_and_survive_failures():
    seen = threading.Event()

    def broken(user_id):
        raise RuntimeError("boom")

    events.subscribe("test_event", broken)
    events.subscribe("test_event", lambda user_id: seen.set())
    events.publish("test_event", "u1")
    assert seen.wait(2)
