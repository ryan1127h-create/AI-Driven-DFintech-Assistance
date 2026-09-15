"""End-to-end smoke test for the redesigned course_recommendation workflow:
runs the whole 6-STAGE pipeline through the public interface with the LLM
call forced to fail, so every group is filled by the deterministic
fallback — this exercises the real STAGE sequence, diagnostics, and the
grouped response shape without depending on a live model."""

from __future__ import annotations

from app.domains.specialist.course_recommendation import interface
from app.domains.specialist.course_recommendation.pipeline import selection


def _request() -> dict:
    return {
        "background": {"completed_courses": []},
        "course_catalog": [
            {
                "code": "BMD5301", "title": "Intro to Finance", "units": 4,
                "section": "Core Courses", "can_recommend": True,
            },
            {
                "code": "BMD5302", "title": "Financial Modelling", "units": 4,
                "section": "Core Courses", "can_recommend": True,
            },
            {
                "code": "IT5001X", "title": "Software Dev Fundamentals", "units": 4,
                "section": "Core Courses", "can_recommend": True,
            },
            {
                "code": "IT5006", "title": "Fundamentals of Data Analytics", "units": 4,
                "section": "Core Courses", "can_recommend": True,
            },
            {
                "code": "FT5001", "title": "FinTech Innovations", "units": 4,
                "section": "Core Courses", "can_recommend": True,
                "skills": ["product"],
            },
            {
                "code": "CS4221", "title": "Database Applications", "units": 4,
                "section": "Vertical #1", "can_recommend": True,
                "vertical": ["Vertical #1. Computing Technologies"],
                "skills": ["data_analytics"],
            },
        ],
        "curriculum_rules": [
            {
                "rule_key": "rule:cur_degree_structure", "category": "structure",
                "intake": "2026-08-onwards", "text": "52 units total.",
            }
        ],
        "evidence_sources": ["knowledge base course catalog"],
    }


def test_full_workflow_produces_grouped_recommendations_via_fallback(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("no network in tests")

    monkeypatch.setattr(selection.llm, "complete", _raise)

    result = interface.recommend_courses(_request())

    assert result["workflow_status"] == "degraded"  # no role profile supplied
    slot_types = {g["slot_type"] for g in result["groups"]}
    assert "core_mandatory" in slot_types
    assert "core_choice" in slot_types
    assert "elective" in slot_types

    mandatory_group = next(g for g in result["groups"] if g["slot_type"] == "core_mandatory")
    assert mandatory_group["required_pick_count"] == 2
    # 4 mandatory courses are all still eligible, so all 4 are shown
    # (required 2 + 2 extra, capped at the 4 that actually exist) — not
    # just the 2 that are strictly required.
    assert len(mandatory_group["recommendations"]) == 4
    assert {r["course_code"] for r in mandatory_group["recommendations"]} == {
        "BMD5301", "BMD5302", "IT5001X", "IT5006",
    }
    recommended_flags = [r["recommended"] for r in mandatory_group["recommendations"]]
    assert recommended_flags == [True, True, False, False]

    assert result["degree_progress"] is not None
    assert result["degree_progress"]["core_choice_remaining_count"] == 3

    stage_names = [s["stage"] for s in result["stage_results"]]
    assert "catalog_classification" in stage_names
    assert "degree_progress_computation" in stage_names
    assert "requirement_slot_derivation" in stage_names
    assert "slot_selection" in stage_names

    slot_selection_stages = [s for s in result["stage_results"] if s["stage"] == "slot_selection"]
    assert all(s["status"] == "degraded" for s in slot_selection_stages)


def test_scoping_to_specific_codes_restricts_recommendations(monkeypatch):
    monkeypatch.setattr(
        selection.llm, "complete", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm"))
    )
    request = _request()
    request["constraints"] = {"candidate_course_codes": ["CS4221"]}

    result = interface.recommend_courses(request)

    all_codes = {
        r["course_code"] for g in result["groups"] for r in g["recommendations"]
    }
    assert all_codes <= {"CS4221"}
