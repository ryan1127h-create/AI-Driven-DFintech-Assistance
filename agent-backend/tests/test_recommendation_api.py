from fastapi import FastAPI
from fastapi.testclient import TestClient

from student.api2 import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _profile(**overrides):
    base = {
        "lifecycle_stage": "current",
        "target_roles": ["fintech_pm"],
        "completed_modules": ["BMS5312"],
        "technical_proficiency": "intermediate",
        "finance_knowledge": "basic",
        "work_domain": "banking",
        "personalization": True,
    }
    base.update(overrides)
    return base


def test_courses_recommendation_endpoint_returns_backend_plan():
    resp = _client().post(
        "/api/recommend/courses",
        json={"profile": _profile(), "target_role": "fintech_pm"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["agentStatus"]["status"] == "ok"
    assert body["data"]["recommended"]
    assert "BMS5312" not in {m["code"] for m in body["data"]["recommended"]}
    assert body["data"]["progress"]["completed"] >= 4


def test_career_recommendation_endpoint_returns_skill_gap_modules():
    resp = _client().post(
        "/api/recommend/career",
        json={"profile": _profile(target_roles=[]), "target_role": "payments"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["targetRole"] == "payments"
    assert body["data"]["requiredSkills"]
    assert body["data"]["careerSkillGaps"]
    assert body["data"]["gapClosingModules"]


# ---------- no silent coercion at the wire boundary ----------
def test_unmappable_lifecycle_stage_is_rejected_with_the_offending_value():
    """Regression: an unrecognised stage used to become `current` silently.

    A mistyped stage then had the checklist and tracker advising an alumnus as if
    they were still enrolled, so it has to fail loudly and say what it received.
    """
    resp = _client().post(
        "/api/recommend/courses",
        json={"profile": _profile(lifecycle_stage="alumnus")},
    )

    assert 400 <= resp.status_code < 500
    assert "alumnus" in resp.text


def test_alumni_stage_is_not_rewritten_into_a_current_student():
    """Regression: `alumni` was spelled correctly yet re-defaulted to `current`.

    The alumni flow supports neither intent, so the honest answer is the
    supervisor's advisory -- not a course plan the user cannot enrol in.
    """
    resp = _client().post(
        "/api/recommend/courses",
        json={"profile": _profile(lifecycle_stage="alumni")},
    )

    body = resp.json()
    assert body["ok"] is False
    assert body["agentStatus"]["status"] == "need_clarification"
    assert "alumni" in body["agentStatus"]["speakable"].lower()
    assert body["data"]["recommended"] == []


def test_unknown_target_role_is_rejected_instead_of_being_dropped():
    resp = _client().post(
        "/api/recommend/courses",
        json={"profile": _profile(target_roles=["fintech_pm", "bogus_role"])},
    )

    assert 400 <= resp.status_code < 500
    assert "bogus_role" in resp.text


def test_three_level_tech_word_is_rejected_rather_than_read_as_unknown():
    """`strong` is the RAG pipeline's 3-level word; mapping it is the adapter's
    job. Accepting it here would have silently discarded the user's skill level.
    """
    resp = _client().post(
        "/api/recommend/courses",
        json={"profile": _profile(technical_proficiency="strong")},
    )

    assert 400 <= resp.status_code < 500
    assert "strong" in resp.text


# ---------- which target role gets advised on ----------
def test_an_explicit_target_role_leads_even_when_the_profile_already_lists_it():
    """Regression: the override only jumped the queue when it was NOT listed.

    `target_roles` here already names payments, in second place. The old
    `if override not in ordered` guard therefore left the order untouched and
    fintech_pm stayed primary; the request was answered correctly only because a
    duplicate `target_role` slot shadowed the profile entirely.
    """
    resp = _client().post(
        "/api/recommend/career",
        json={
            "profile": _profile(target_roles=["fintech_pm", "payments"]),
            "target_role": "payments",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["targetRole"] == "payments"


def test_without_an_override_the_first_listed_role_is_the_one_advised_on():
    """No override: order is the user's, and index 0 is the primary role."""
    resp = _client().post(
        "/api/recommend/career",
        json={"profile": _profile(target_roles=["payments", "fintech_pm"])},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["targetRole"] == "payments"


# ---------- error responses ----------
def test_agent_failure_returns_a_json_error_body(monkeypatch):
    """Regression: _json_error returned the set literal `{(payload), status}`.

    Dicts are unhashable, so building it raised TypeError inside the except
    block and destroyed the original error instead of reporting it.
    """
    def _explode(*args, **kwargs):
        raise RuntimeError("navigator unavailable")

    monkeypatch.setattr("student.api2.route", _explode)

    resp = _client().post("/api/recommend/courses", json={"profile": _profile()})

    assert resp.status_code == 500
    assert resp.json() == {"ok": False, "error": "navigator unavailable"}
