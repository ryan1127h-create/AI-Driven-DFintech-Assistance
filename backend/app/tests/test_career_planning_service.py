"""Exercises career planning end to end through its public interface: one
input report in, each mode's result out — and the failures and
degradations the workflow reports."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.specialist.career_planning import workflow
from app.domains.specialist.career_planning.errors import CareerPlanningStageError, ErrorCode
from app.domains.specialist.career_planning.interface import plan_career

ROLES = [
    {"tag": "data_analytics", "name": "Data Analytics", "required_skills": ["data_analytics", "programming", "finance"]},
    {"tag": "data_engineering", "name": "Data Engineering",
     "required_skills": ["data_engineering", "programming", "data_analytics"]},
    {"tag": "machine_learning_ai", "name": "Machine Learning & AI",
     "required_skills": ["ai_ml", "data_analytics", "programming"]},
    {"tag": "quantitative_finance", "name": "Quantitative Finance",
     "required_skills": ["programming", "finance", "risk_modeling", "data_analytics"]},
    {"tag": "cybersecurity", "name": "Cybersecurity", "required_skills": ["security", "programming", "regulation"]},
    {"tag": "regulation_governance", "name": "Regulation & Governance",
     "required_skills": ["regulation", "security", "risk_modeling", "finance"]},
]
LINKS = [
    {"code": "FT5005", "title": "Machine Learning in Finance", "tags": ["machine_learning_ai", "data_analytics"]},
    {"code": "IT5001X", "title": "Software Development", "tags": ["data_engineering"]},
    {"code": "BMD5302", "title": "Financial Modeling", "tags": ["quantitative_finance"]},
]
PROFILE = {
    "code_level": 3, "degree_discipline_category": "cs_se", "tech_stack": ["python", "sql"],
    "math_stats_level": 2, "function_experience": [{"key": "data_ai", "internship": True}],
    "current_courses": ["FT5005", "IT5001X"],
}
SITUATION = {"stage": "current", "expected_grad_term": "AY2027/28 Sem1", "target_markets": ["SG"]}


def _report(mode, roles=(), **overrides):
    report = {
        "request_id": "r1", "mode": mode, "today": date(2026, 10, 13), "target_roles": list(roles),
        "preferred_roles": ["data_engineering"], "profile": PROFILE, "situation": SITUATION,
        "role_catalog": ROLES, "course_links": LINKS, "evidence_sources": ["Role tags"],
    }
    report.update(overrides)
    return report


def test_exploration_ranks_the_roles_that_fit_best():
    result = plan_career(_report("exploration"))
    assert result["mode"] == "exploration" and result["workflow_status"] == "complete"
    tags = [r["role"]["tag"] for r in result["roles"]]
    assert len(tags) == 4 and tags[0] in {"data_analytics", "machine_learning_ai", "data_engineering"}
    assert "regulation_governance" not in tags
    assert result["roadmap"] is None and result["comparison"] is None
    # The skills shown are those the shown roles need.
    needed = {s for r in result["roles"] for s in r["role"]["required_skills"]}
    assert {s["skill"] for s in result["skills"]} == needed
    assert result["sources"] == ["Role tags"]


def test_exploration_keeps_a_listed_role_that_ranks_low():
    report = _report("exploration", preferred_roles=["regulation_governance"])
    tags = [r["role"]["tag"] for r in plan_career(report)["roles"]]
    assert len(tags) == 5 and tags[-1] == "regulation_governance"


def test_plan_grades_the_roles_skills_and_dates_the_roadmap():
    result = plan_career(_report("plan", ["quantitative_finance"]))
    (fit,) = result["roles"]
    assert fit["role"]["tag"] == "quantitative_finance"
    statuses = {s["skill"]: s["status"] for s in result["skills"]}
    # data analytics: an internship in data / AI (0.5), SQL (0.4) and maths level 2 (0.4).
    assert statuses == {"programming": "met", "data_analytics": "met", "finance": "unknown",
                        "risk_modeling": "unknown"}
    phases = [p["kind"] for p in result["roadmap"]["phases"]]
    # Recording the two unknown skills starts now, before applications open.
    assert phases == ["build_up", "capstone_applications", "capstone_internship", "job_search"]
    build_up = result["roadmap"]["phases"][0]
    assert build_up["start"] == "2026-10-13" and build_up["actions"][0]["kind"] == "evidence"
    assert result["roadmap"]["capstone_cycle_year"] == 2027
    assert any("2027 Capstone dates" in n for n in result["notes"])
    assert fit["support"] == {"course_codes": ["BMD5302"], "taken": [], "taking": []}


def test_compare_sets_the_roles_side_by_side():
    result = plan_career(_report("compare", ["data_analytics", "data_engineering"]))
    assert [r["role"]["tag"] for r in result["roles"]] == ["data_analytics", "data_engineering"]
    assert result["comparison"] == {
        "shared_skills": ["data_analytics", "programming"],
        "distinct_skills": {"data_analytics": ["finance"], "data_engineering": ["data_engineering"]},
    }
    assert result["roadmap"] is None


def test_an_empty_profile_is_answered_with_every_skill_unknown():
    result = plan_career(_report("plan", ["data_analytics"], profile={}, situation={}))
    assert not result["has_profile_evidence"]
    assert {s["status"] for s in result["skills"]} == {"unknown"}
    codes = {d["code"] for d in result["diagnostics"]}
    assert {ErrorCode.NO_PROFILE_EVIDENCE, ErrorCode.LOW_CONFIDENCE_FIT, ErrorCode.NO_GRADUATION_TERM} <= codes
    assert any("doesn't yet hold any skill evidence" in n for n in result["notes"])


def test_an_invalid_report_fails_validation():
    with pytest.raises(CareerPlanningStageError) as error:
        plan_career(_report("plan"))
    assert error.value.code == ErrorCode.INPUT_INVALID and error.value.status_code == 422


def test_a_failing_roadmap_degrades_the_plan(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(workflow.planner, "build_roadmap", broken)
    result = plan_career(_report("plan", ["data_analytics"]))
    assert result["workflow_status"] == "degraded" and result["roadmap"] is None
    assert result["skills"]
    assert ErrorCode.ROADMAP_FAILED in {d["code"] for d in result["diagnostics"]}


def test_a_failing_required_stage_fails_the_request(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(workflow.skills, "assess_skills", broken)
    with pytest.raises(CareerPlanningStageError) as error:
        plan_career(_report("plan", ["data_analytics"]))
    assert error.value.stage == "skill_evidence"
    assert error.value.stage_results[-1].status == "failed"
