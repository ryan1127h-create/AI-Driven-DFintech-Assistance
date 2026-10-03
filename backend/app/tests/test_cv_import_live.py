"""CV extraction against the live field dictionary and the real LLM, on a
made-up CV — read-only: the candidates are checked but never stored.

Skipped unless RUN_LIVE_DB_TESTS=1.

    RUN_LIVE_DB_TESTS=1 pytest app/tests/test_cv_import_live.py
"""

from __future__ import annotations

import os

import pytest

from app.domains.cv_import.service import check_candidates
from app.domains.profile import service as profile_service
from app.domains.specialist.cv_extraction.interface import extract_fields

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_DB_TESTS") != "1", reason="set RUN_LIVE_DB_TESTS=1 to run against the live database"
)

SAMPLE_CV = """\
ALEX LIM
Singapore | alex.lim@example.com

EDUCATION
National University of Singapore — Bachelor of Science in Statistics, 2022
Second Class Upper Honours. Medium of instruction: English.
Relevant modules: Probability & Statistics, Linear Algebra, Econometrics, Programming Methodology

EXPERIENCE
Data Analyst, DBS Bank, Singapore (Jul 2022 – present)
- Built Python and SQL pipelines for credit-risk reporting dashboards in Tableau
- Worked with the AML compliance team on transaction monitoring rules

CERTIFICATIONS
FRM Part I (passed 2024)

SKILLS
Python, SQL, R, Tableau, Git

TEST SCORES
GRE 325 (taken 2025-03-10)
"""


def _targets_for(stage: str) -> list[dict]:
    definitions = profile_service.repository.load_field_definitions()
    code = profile_service.STAGE_CODES[stage]
    return [
        {k: d[k] for k in profile_service._CV_TARGET_KEYS}
        for key, d in definitions.items()
        if "CV" in (d["sources"] or []) and d["extraction_type"] == "literal"
        and key not in profile_service.SELF_RATED_FIELDS and code in (d["stages"] or [])
    ]


def test_sample_cv_yields_checked_candidates():
    targets = _targets_for("prospect")
    candidates = check_candidates(extract_fields(SAMPLE_CV, targets), targets, SAMPLE_CV)

    assert candidates["highest_degree"]["value"] == "bachelor"
    assert candidates["degree_discipline_category"]["value"] == "math_stats_physics"
    assert {"python", "sql"} <= set(candidates["tech_stack"]["value"])
    assert any(t["key"] == "GRE" for t in candidates["admission_tests"]["value"])
    for key in ("total_work_years", "seniority_level", "code_level"):
        assert key not in candidates  # asked directly or self-rated, never taken from a CV
    assert "research_output" not in candidates  # not mentioned is not "none"
    for candidate in candidates.values():
        assert candidate["quote"].casefold().split()[0] in SAMPLE_CV.casefold()
