"""Career planning against the live database — read-only: the knowledge
base yields a role catalogue and course links the domain's contract
accepts, and every mode runs on them (without the LLM steps).

Skipped unless RUN_LIVE_DB_TESTS=1.

    RUN_LIVE_DB_TESTS=1 pytest app/tests/test_career_planning_live.py
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from app.domains.specialist.career_planning.interface import plan_career
from app.domains.specialist.career_planning.policy import skill_evidence
from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly.builder import build_report
from app.tools.specialist.career_planning.s2_assembly.prefetch import prefetch, role_catalog

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)


def test_every_role_names_skills_from_the_evidence_vocabulary():
    catalog = role_catalog()
    assert len(catalog) == 12
    for role in catalog:
        assert set(role["required_skills"]) <= set(skill_evidence.SKILLS)


@pytest.mark.parametrize("hint, roles", [
    ("exploration", []),
    ("plan", ["quantitative_finance"]),
    ("compare", ["data_analytics", "data_engineering"]),
])
def test_each_mode_runs_on_the_live_catalogue(hint, roles):
    built = build_report(prefetch(None), ParsedCareerRequest(roles=roles), hint, date(2026, 10, 13))
    result = plan_career(built.report)
    assert result["mode"] == hint and result["roles"]
    assert all(f["support"]["course_codes"] for f in result["roles"])
