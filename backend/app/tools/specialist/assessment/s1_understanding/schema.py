"""
S1 — what an assessment message states about the applicant, in the
profile's own field keys and values, so it can be laid over the profile
and offered for saving. The allowed values are the profile dictionary's
(profile.field_definitions); test_assessment_live.py checks they still
match it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HIGHEST_DEGREES = ("bachelor", "master", "phd", "other")
DISCIPLINES = ("cs_se", "information_systems", "engineering", "math_stats_physics", "finance_econ_accounting",
               "business_mgmt", "other_social_science", "humanities_other")
GPA_BANDS = ("top_10pct", "first_class_equiv", "second_upper_equiv", "second_lower_equiv", "below")
TEST_KEYS = ("GRE", "GMAT", "GATE", "TOEFL", "IELTS")
TECH_STACK = ("python", "r", "sql", "java", "cpp", "javascript", "solidity", "matlab", "excel_vba", "bloomberg",
              "tableau_powerbi", "cloud", "git", "docker", "spark")
COURSEWORK = ("programming", "dsa", "databases", "machine_learning", "linear_algebra", "probability_statistics",
              "econometrics", "stochastic_calculus", "corporate_finance", "investments_derivatives", "accounting")
WORK_YEARS = ("0", "<1", "1-3", "3-5", "5-10", "10+")
FUNCTIONS = ("engineering", "data_ai", "quant", "risk_compliance", "product_business", "operations", "sales_client",
             "research")
RESEARCH = ("none", "thesis_only", "conference", "journal", "multiple_journal")
CERTIFICATIONS = ("cfa", "frm", "cqf", "cpa_acca", "cloud_cert", "pmp", "other")

SINGLE_CHOICES = {
    "highest_degree": HIGHEST_DEGREES, "degree_discipline_category": DISCIPLINES, "gpa_band": GPA_BANDS,
    "total_work_years": WORK_YEARS, "research_output": RESEARCH,
}
MULTI_CHOICES = {
    "tech_stack": TECH_STACK, "prior_coursework": COURSEWORK, "function_experience": FUNCTIONS,
    "certifications": CERTIFICATIONS,
}
LEVELS = {"code_level": (0, 4), "math_stats_level": (1, 3), "finance_level": (1, 3)}


@dataclass(frozen=True)
class StatedFacts:
    """field key -> value for the facts the message states; values already
    checked against the allowed sets. `parse_failed`: the parser couldn't
    run, so nothing was read from the message."""

    values: dict = field(default_factory=dict)
    parse_failed: bool = False
