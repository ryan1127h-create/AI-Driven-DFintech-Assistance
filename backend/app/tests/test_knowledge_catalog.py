"""The knowledge layer's structured reads on an in-memory adapter:
course rows (workload, corequisites split out of the prerequisite text),
role tags and course tags,
free-text role matching, chunk topics — and the course-recommendation
tool's per-course skills built from role tags."""

from __future__ import annotations

import pytest

from app.domains.knowledge_retrieval import service
from app.tools.specialist.course_recommendation.s2_assembly import mappers


def _course(code, *, section="Core Courses", active=True, prereq=None, preclusion=(), workload=None):
    return {
        "course_code": code, "title": f"Course {code}", "annex_section": section, "annex_intake": "2026",
        "module_credit": 4, "description": "About it.",
        "needs_review": False, "source_url": None, "can_recommend": active, "workload": workload,
        "prerequisite_grad_text": prereq, "corequisite_grad_text": None, "preclusion_codes": list(preclusion),
        "current_ay_label": "2026-2027", "current_ay_semesters": [1],
    }


ROLE_TAGS = [
    {"tag": "data_analytics", "name_en": "Data Analytics", "definition": "",
     "required_skills": ["data_analytics", "programming", "finance"]},
    {"tag": "machine_learning_ai", "name_en": "Machine Learning & AI", "definition": "",
     "required_skills": ["ai_ml", "data_analytics", "programming"]},
    {"tag": "blockchain", "name_en": "Blockchain", "definition": "",
     "required_skills": ["payments_systems", "programming"]},
]


class _KB:
    courses = [
        _course("FT5005", workload=[3, 0, 0, 5, 2]),
        _course("FT5007", section="Capstone Project", active=False,
                prereq="Must have completed IT5001X | 并修(coreq): Must concurrently take IT5006"),
        _course("IT5004", prereq="并修(coreq): Must be concurrently enrolled in IT5001 or IT5001X"),
        _course("IT5001", section=None),  # earlier intake only
        _course("IT5006", preclusion=("BT5126", "CS5228")),
    ]

    def fetch_all_courses(self):
        return self.courses

    def fetch_role_tags(self):
        return ROLE_TAGS

    def fetch_course_tags(self):
        return [{"course_code": "FT5005", "tag": "data_analytics"},
                {"course_code": "FT5005", "tag": "machine_learning_ai"},
                {"course_code": "IT5006", "tag": "blockchain"}]


@pytest.fixture()
def kb(monkeypatch):
    fake = _KB()
    monkeypatch.setattr(service, "knowledge_db", fake)
    return fake


def test_courses_split_corequisites_and_float_workload(kb):
    rows = {r["course_code"]: r for r in service.list_courses()}
    assert rows["FT5005"]["workload"] == [3.0, 0.0, 0.0, 5.0, 2.0]
    assert (rows["FT5007"]["prerequisite_grad_text"], rows["FT5007"]["corequisite_grad_text"]) == (
        "Must have completed IT5001X", "Must concurrently take IT5006")
    assert (rows["IT5004"]["prerequisite_grad_text"], rows["IT5004"]["corequisite_grad_text"]) == (
        None, "Must be concurrently enrolled in IT5001 or IT5001X")
    assert rows["IT5001"]["prerequisite_grad_text"] is None


def test_role_tags_and_course_tags(kb):
    assert service.get_role_profile("blockchain") == {
        "role_id": "blockchain", "role_title": "Blockchain", "required_skills": ["payments_systems", "programming"]}
    assert service.get_role_profile("astrology") is None
    assert service.list_course_tags() == {"FT5005": ["data_analytics", "machine_learning_ai"], "IT5006": ["blockchain"]}


@pytest.mark.parametrize("text, tag", [
    ("data_analytics", "data_analytics"),
    ("I want to work in Machine Learning & AI", "machine_learning_ai"),
    ("machine learning and ai", "machine_learning_ai"),
    ("a BLOCKCHAIN developer", "blockchain"),
    ("quant trader", None),
    ("", None),
])
def test_match_role_tag(kb, text, tag):
    assert service.match_role_tag(text) == tag


def test_role_tag_chunks_are_career_topic():
    assert service._topic_of("tags_definition", {}) == "career"
    assert service._topic_of("courses", {}) == "academic"


def test_course_skills_are_the_union_of_their_tags_skills():
    skills = mappers.course_skills(
        {"FT5005": ["data_analytics", "machine_learning_ai"], "IT5006": ["blockchain"]}, ROLE_TAGS)
    assert skills == {
        "FT5005": ["data_analytics", "programming", "finance", "ai_ml"],
        "IT5006": ["payments_systems", "programming"],
    }

