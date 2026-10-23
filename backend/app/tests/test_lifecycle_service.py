"""lifecycle.service — the stage gate, the enrolled courses, and degree
progress from completed courses alone vs. with current ones counted — on
in-memory stand-ins for sis, profile and the knowledge base."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ForbiddenError
from app.domains.auth.interface import get_current_user_id
from app.domains.lifecycle import service

COURSES = [
    {"course_code": "BMD5301", "title": "Financial Markets", "module_credit": 4},
    {"course_code": "IT5001X", "title": "Software Development", "module_credit": 4},
    {"course_code": "FT5005", "title": "Machine Learning in Finance", "module_credit": 4},
    {"course_code": "CS5228", "title": "Knowledge Discovery", "module_credit": 4},
]
ELECTIVES = {"CS5228": ["vertical_2"]}
ENROLLMENTS = [
    {"course_code": "BMD5301", "term": "AY2025/26 Sem2", "status": "completed", "grade_band": "A", "credits": 4},
    {"course_code": "FT5005", "term": "AY2025/26 Sem2", "status": "completed", "grade_band": "B+", "credits": 4},
    {"course_code": "IT5001X", "term": "AY2026/27 Sem1", "status": "current", "grade_band": None, "credits": 4},
    {"course_code": "CS5228", "term": "AY2026/27 Sem1", "status": "current", "grade_band": None, "credits": 4},
]
RECORD = {
    "study_mode": "full_time", "track_chosen": "financial_data_analytics_intelligence",
    "enrolled_at": datetime(2025, 8, 10, tzinfo=timezone.utc), "academic_standing": "good",
    "gpa_current_band": ">=3.0", "expected_grad_term": "AY2026/27 Sem2", "graduation_term": None,
}
LABELS = {"full_time": "Full-time", "financial_data_analytics_intelligence": "Financial Data Analytics and Intelligence"}


@pytest.fixture()
def stage(monkeypatch):
    current = {"value": "current"}
    monkeypatch.setattr(service.profile_interface, "get_profile_field", lambda user_id, key: current["value"])
    monkeypatch.setattr(service.profile_interface, "describe_value", lambda key, value: LABELS.get(value, value))
    monkeypatch.setattr(service.knowledge, "list_courses", lambda: COURSES)
    monkeypatch.setattr(service.knowledge, "list_course_electives", lambda: ELECTIVES)
    monkeypatch.setattr(service.sis, "list_enrollments", lambda user_id: ENROLLMENTS)
    monkeypatch.setattr(service.sis, "get_academic_record", lambda user_id: RECORD)
    monkeypatch.setattr(service.sis, "get_program", lambda code: {"program_name": "MSc DFT", "total_credit_required": 52})
    return current


@pytest.mark.parametrize("value", ["prospect", "applicant", "admitted", "alumni", None])
def test_only_current_and_graduating_students_have_a_lifecycle(stage, value):
    stage["value"] = value
    with pytest.raises(ForbiddenError):
        service.get_lifecycle("u1")


def test_record_and_courses(stage):
    result = service.get_lifecycle("u1")
    assert result.programme.total_units_required == 52
    assert (result.record.study_mode, result.record.track) == ("Full-time", "Financial Data Analytics and Intelligence")
    roles = {c.course_code: (c.title, c.status, c.requirement_role) for c in result.courses}
    assert roles == {
        "BMD5301": ("Financial Markets", "completed", "core_mandatory"),
        "FT5005": ("Machine Learning in Finance", "completed", "core_choice"),
        "IT5001X": ("Software Development", "current", "core_mandatory"),
        "CS5228": ("Knowledge Discovery", "current", "elective"),
    }


def test_progress_counts_current_courses_only_in_the_projection(stage):
    result = service.get_lifecycle("u1")
    done, projected = result.progress, result.projected_progress
    assert (done.total_units_done, projected.total_units_done) == (8, 16)
    assert done.core_mandatory_done == ["BMD5301"]
    assert projected.core_mandatory_done == ["BMD5301", "IT5001X"]
    assert (done.core_choice_remaining_count, done.elective_units_done, projected.elective_units_done) == (2, 0, 4)
    assert done.total_units_target == 52


def test_progress_text_quotes_the_computed_units(stage, monkeypatch):
    enrollments = ENROLLMENTS + [
        {"course_code": "FT5007", "term": "AY2026/27 Sem1", "status": "current", "grade_band": None, "credits": 12},
        {"course_code": "CS5228", "term": "AY2026/27 Sem2", "status": "planned", "grade_band": None, "credits": 4},
    ]
    monkeypatch.setattr(service.sis, "list_enrollments", lambda user_id: enrollments)
    text = service.progress_text("u1")
    assert "8 of 52 completed; 20 in progress this semester" in text and "FT5007: 12 units" in text
    assert "Planned for later: CS5228: 4 units" in text


def test_progress_text_is_none_before_enrolment(stage):
    stage["value"] = "admitted"
    assert service.progress_text("u1") is None


def test_endpoint_returns_403_before_enrolment(stage):
    from app.main import app

    stage["value"] = "applicant"
    app.dependency_overrides[get_current_user_id] = lambda: "u1"
    try:
        response = TestClient(app).get("/api/v1/lifecycle")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
