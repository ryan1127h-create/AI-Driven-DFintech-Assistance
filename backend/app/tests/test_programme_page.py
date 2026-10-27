"""programme_page: the public programme page — built from the catalogue,
the course and role data and shared alumni stories (in-memory stand-ins),
open without a token, and naming alumni only for signed-in readers."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.programme_page import service

PROGRAM = {
    "is_target": True, "name": "Master of Science in Digital Financial Technology", "short_name": "MSc DFinTech",
    "summary": "A 52-Unit coursework master's.", "official_url": "https://example.edu/mdft/", "intake_year": 2027,
    "verified_at": date(2026, 10, 14),
    "facts": {"study_modes": ["full_time", "part_time"], "duration_ft_months": 18, "duration_pt_months": 30,
              "total_credits": 52, "credit_unit": "NUS Units", "intake_months": [8], "toefl_ibt_min": 90,
              "ielts_min": 6, "english_waiver": "Not needed after an English-medium degree.",
              "gmat_gre_policy": "recommended", "work_exp_policy": "not_required", "application_fee": 109,
              "application_fee_currency": "SGD"},
    "sources": {"total_credits": [{"source_url": "https://example.edu/mdft/", "role": "primary"}]},
    "fees": [{"student_category": "all", "amount": 76409, "currency": "SGD", "includes_tax": True, "note": None,
              "source_url": "https://example.edu/fees"}],
    "deadlines": [{"round_label": "August intake", "opens_on": date(2026, 10, 1), "closes_on": date(2027, 1, 31),
                   "source_url": "https://example.edu/apply"}],
    "funding": [{"name": "Tuition Fee Rebate", "kind": "rebate", "percent": 40, "amount": None, "currency": None,
                 "eligible_categories": ["sg_citizen", "sg_pr"], "conditions": None, "source_url": None}],
    "curriculum": [{"skill_id": "ai_ml", "coverage": "core_option", "evidence_courses": ["FT5005"], "source_url": None},
                   {"skill_id": "finance", "coverage": "required", "evidence_courses": ["BMD5301"], "source_url": None}],
}
COURSES = [
    {"course_code": "BMD5301", "title": "Finance", "module_credit": 4, "description": "Intro."},
    {"course_code": "FT5005", "title": "ML for Finance", "module_credit": 4, "description": "x " * 400},
    {"course_code": "FT5007", "title": "Capstone", "module_credit": 12, "description": None},
    {"course_code": "BT4016", "title": "Risk Analytics", "module_credit": 4, "description": None},
]
STORY = {"name": "Daniel Tan", "position": "Quant", "company": "DBS", "class_year": 2024, "bio": "Pricing models.",
         "expertise": ["Quantitative Finance"]}


@pytest.fixture(autouse=True)
def world(monkeypatch):
    service._cache.update(at=0.0, page=None)
    k = service.knowledge
    monkeypatch.setattr(service.program_catalog, "list_programs", lambda: [PROGRAM, {**PROGRAM, "is_target": False}])
    monkeypatch.setattr(k, "list_courses", lambda: COURSES)
    monkeypatch.setattr(k, "list_course_electives", lambda: {"BT4016": ["Vertical #3. Risk"]})
    monkeypatch.setattr(k, "list_curriculum_rules", lambda: [{"content": "52 units in total."}])
    monkeypatch.setattr(k, "list_admissions_items", lambda: {
        "cv": {"label": "CV", "description": None, "required": True},
        "gre": {"label": "GRE", "description": None, "required": False}})
    monkeypatch.setattr(k, "list_course_tags", lambda: {"FT5005": ["machine_learning_ai"]})
    monkeypatch.setattr(k, "list_role_tags", lambda: [{"tag": "machine_learning_ai", "name_en": "Machine Learning & AI",
                                                       "definition": "Models.", "required_skills": ["ai_ml"]}])
    monkeypatch.setattr(service.alumni, "showcase_stories", lambda: [STORY])
    yield
    service._cache.update(at=0.0, page=None)


def test_the_page_follows_the_catalogue_and_the_curriculum_rules():
    page = service.get_page(True)
    facts = {f["label"]: f["value"] for f in page["programme"]["key_facts"]}
    assert facts["Duration"] == "18 months full-time · 30 months part-time"
    assert facts["Applications"] == "1 Oct 2026 – 31 Jan 2027" and facts["Tuition"] == "S$76,409 incl. GST"
    curriculum = page["curriculum"]
    assert [c["code"] for c in curriculum["core_mandatory"]] == ["BMD5301"]
    assert [c["code"] for c in curriculum["core_choice"]] == ["FT5005"]
    assert [c["code"] for c in curriculum["capstone"]] == ["FT5007"]
    assert curriculum["verticals"] == [{"name": "Vertical #3. Risk", "courses": [
        {"code": "BT4016", "title": "Risk Analytics", "units": 4, "description": None}]}]
    assert curriculum["core_choice"][0]["description"].endswith("…")
    # required areas first
    assert [a["coverage"] for a in curriculum["skill_areas"]] == ["Required core", "Core option"]
    english = next(r for r in page["admissions"]["requirements"] if r["label"] == "English")["value"]
    assert english.startswith("TOEFL iBT 90 or IELTS 6.0.")
    assert [d["label"] for d in page["admissions"]["documents"]] == ["CV", "GRE"]
    assert page["fees"]["funding"][0]["amount"] == "40% of tuition"
    assert page["careers"][0]["courses"] == [{"code": "FT5005", "title": "ML for Finance"}]


def test_alumni_are_named_only_for_signed_in_readers():
    assert service.get_page(True)["stories"][0]["name"] == "Daniel Tan"
    visitor = service.get_page(False)["stories"][0]
    assert visitor["name"] is None and visitor["company"] == "DBS"


def test_the_page_opens_without_a_token():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.errors import register_error_handlers
    from app.domains.programme_page.api import router

    app = FastAPI()
    app.include_router(router)
    register_error_handlers(app)
    http = TestClient(app)
    response = http.get("/programme/overview")
    assert response.status_code == 200 and response.json()["stories"][0]["name"] is None
    # an invalid token is a visitor, not an error
    response = http.get("/programme/overview", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 200 and response.json()["stories"][0]["name"] is None
