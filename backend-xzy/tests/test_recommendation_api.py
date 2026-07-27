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
