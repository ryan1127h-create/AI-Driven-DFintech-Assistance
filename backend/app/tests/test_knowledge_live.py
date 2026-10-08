"""The knowledge layer against the live database — read-only: the
catalogue assembles from the course tables, every course carries role
tags whose skills the recommender accepts, and a full course recommendation runs on
the real catalogue (without the LLM reply step).

Skipped unless RUN_LIVE_DB_TESTS=1.

    RUN_LIVE_DB_TESTS=1 pytest app/tests/test_knowledge_live.py
"""

from __future__ import annotations

import os
import re

import pytest

from app.domains.knowledge_retrieval import service
from app.domains.specialist.course_recommendation.interface import recommend_courses
from app.tools.specialist.course_recommendation.s2_assembly.builder import build_request

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)

_CJK = re.compile(r"[一-鿿]")


def test_catalogue_assembles_every_course():
    courses = service.list_courses()
    assert len(courses) == 57
    for c in courses:
        assert c["title"] and c["description"], c["course_code"]
        assert c["workload"] is None or len(c["workload"]) == 5
        assert not _CJK.search(c["prerequisite_grad_text"] or ""), c["course_code"]
    active_without_schedule = [c["course_code"] for c in courses if c["can_recommend"] and not c["current_ay_semesters"]]
    assert active_without_schedule == []


def test_every_course_is_tagged_with_known_role_tags():
    tags = {t["tag"]: t for t in service.list_role_tags()}
    assert len(tags) == 12
    assert all(t["name_en"] and t["required_skills"] for t in tags.values())
    course_tags = service.list_course_tags()
    assert {c["course_code"] for c in service.list_courses()} == set(course_tags)
    assert {tag for ts in course_tags.values() for tag in ts} <= set(tags)


def test_role_text_resolves_to_tags():
    assert service.match_role_tag("Machine Learning & AI") == "machine_learning_ai"
    assert service.get_role_profile("data_analytics")["role_title"] == "Data Analytics"


@pytest.mark.parametrize("role", ["data_analytics", None])
def test_course_recommendation_runs_on_the_live_catalogue(role):
    result = recommend_courses(build_request({}, role))
    assert result["workflow_status"] in ("ok", "degraded")
    assert result["groups"] and any(g["recommendations"] for g in result["groups"])
    if role:
        assert result["target_role"] == "Data Analytics"
