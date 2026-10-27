"""The assessment domain: hard conditions (degree, programming or
quantitative preparation, English, timing), soft factors, and the verdict —
pure code on a report, no data access, no LLM."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.specialist.assessment import interface as assessment
from app.domains.specialist.assessment.contracts import ApplicantFacts, Requirements
from app.domains.specialist.assessment.stages import hard, soft

REQ = {"intake_year": 2027, "toefl_ibt_min": 90, "toefl_band_min": 4.5, "ielts_min": 6.0, "gmat_reference": 700,
       "application_opens": "2026-10-01", "application_closes": "2027-01-31"}
TODAY = "2026-10-16"


def _run(facts: dict, today: str = TODAY, **req) -> dict:
    return assessment.assess({"facts": facts, "requirements": {**REQ, **req}, "today": today})


def _hard(result: dict) -> dict:
    return {h["key"]: h["status"] for h in result["hard"]}


def _soft(result: dict) -> dict:
    return {s["key"]: s["status"] for s in result["soft"]}


# --- degree --------------------------------------------------------------------

@pytest.mark.parametrize("discipline, status", [
    ("cs_se", "met"), ("engineering", "met"), ("finance_econ_accounting", "met"), ("business_mgmt", "met"),
    ("humanities_other", "to_confirm"), (None, "to_confirm"),
])
def test_the_degree_condition_follows_the_listed_disciplines(discipline, status):
    assert hard.degree(ApplicantFacts(degree_discipline_category=discipline)).status == status


def test_a_qualification_other_than_a_degree_is_case_by_case():
    check = hard.degree(ApplicantFacts(degree_discipline_category="cs_se", highest_degree="other"))
    assert check.status == "to_confirm" and "case by case" in check.finding


# --- programming or quantitative preparation -------------------------------------

def test_computing_graduates_are_not_asked_for_programming_evidence():
    assert hard.programming_or_quant(ApplicantFacts(degree_discipline_category="cs_se")).status == "exempt"


@pytest.mark.parametrize("facts", [
    {"code_level": 2}, {"tech_stack": ["python"]}, {"prior_coursework": ["programming"]},
    {"prior_coursework": ["econometrics"]}, {"math_stats_level": 2}, {"degree_discipline_category": "math_stats_physics"},
])
def test_python_or_advanced_quantitative_evidence_meets_it(facts):
    assert hard.programming_or_quant(ApplicantFacts(degree_discipline_category=facts.pop("degree_discipline_category",
                                                    "finance_econ_accounting"), **facts)).status == "met"


def test_no_python_with_quant_still_unknown_is_to_confirm_not_a_gap():
    check = hard.programming_or_quant(ApplicantFacts(degree_discipline_category="finance_econ_accounting", code_level=0))
    assert check.status == "to_confirm" and "prior_coursework" in check.missing_fields


def test_no_evidence_on_either_side_is_a_gap():
    check = hard.programming_or_quant(ApplicantFacts(degree_discipline_category="business_mgmt", code_level=1,
                                                     prior_coursework=["accounting"]))
    assert check.status == "gap" and check.action


# --- English ---------------------------------------------------------------------

def _english(facts: dict, deadline: date = date(2027, 1, 31)):
    return hard.english(ApplicantFacts(**facts), Requirements(**REQ), deadline)


def test_an_english_medium_degree_needs_no_test():
    assert _english({"english_medium_degree": True}).status == "exempt"


@pytest.mark.parametrize("test, status", [
    ({"key": "IELTS", "score": 6.5, "test_date": "2025-06-01"}, "met"),
    ({"key": "IELTS", "score": 5.5, "test_date": "2025-06-01"}, "gap"),
    ({"key": "TOEFL", "score": 95, "test_date": "2025-06-01"}, "met"),
    ({"key": "TOEFL", "score": 4.5, "test_date": "2026-03-01"}, "met"),    # the 1-6 band scale
    ({"key": "TOEFL", "score": 4.0, "test_date": "2026-03-01"}, "gap"),
    ({"key": "IELTS", "score": 7.0, "test_date": "2024-12-01"}, "gap"),    # over 2 years old by the deadline
])
def test_english_scores_are_compared_to_the_minimum_and_the_validity(test, status):
    assert _english({"english_medium_degree": False, "admission_tests": [test]}).status == status


def test_unknown_medium_and_no_score_is_to_confirm():
    check = _english({})
    assert check.status == "to_confirm" and check.missing_fields == ("english_medium_degree", "admission_tests")


def test_a_non_english_degree_without_a_score_is_a_gap():
    assert _english({"english_medium_degree": False}).status == "gap"


# --- timing ----------------------------------------------------------------------

def test_timing_follows_the_application_period():
    req = Requirements(**REQ)
    assert "close on 2027-01-31" in hard.timing(req, date(2026, 10, 16)).finding
    assert hard.timing(req, date(2026, 9, 1)).status == "met"
    assert hard.timing(req, date(2027, 2, 1)).status == "to_confirm"


# --- soft factors ------------------------------------------------------------------

def test_relevant_experience_and_research_are_strengths():
    assert soft.relevant_experience(ApplicantFacts(function_experience=["data_ai"])).status == "strength"
    assert soft.relevant_experience(ApplicantFacts(research_output="journal")).status == "strength"
    factor = soft.relevant_experience(ApplicantFacts(function_experience=["sales_client"], total_work_years="1-3"))
    assert factor.status == "improve" and "transferable" in factor.finding


def test_gmat_is_optional_and_compared_to_the_faq_reference():
    req = Requirements(**REQ)
    assert soft.test_scores(ApplicantFacts(admission_tests=[{"key": "GMAT", "score": 720}]), req).status == "strength"
    low = soft.test_scores(ApplicantFacts(admission_tests=[{"key": "GMAT", "score": 650}]), req)
    assert low.status == "improve" and low.optional
    assert soft.test_scores(ApplicantFacts(), req).optional


def test_grades_are_a_competitive_signal_never_a_condition():
    assert soft.academic_record(ApplicantFacts(gpa_band="top_10pct")).status == "strength"
    assert soft.academic_record(ApplicantFacts(gpa_band="second_lower_equiv")).status == "improve"
    assert soft.academic_record(ApplicantFacts()).status == "unknown"


# --- verdict ------------------------------------------------------------------------

def test_a_strong_computing_applicant_meets_every_condition():
    result = _run({"degree_discipline_category": "cs_se", "code_level": 3, "english_medium_degree": True,
                   "function_experience": ["data_ai"], "gpa_band": "first_class_equiv",
                   "admission_tests": [{"key": "GMAT", "score": 720}]})
    assert result["verdict"] == "all_met"
    assert {"programming_depth", "relevant_experience", "test_scores"} <= set(result["strengths"])


def test_any_gap_makes_the_verdict_a_gap_and_unknowns_are_asked_for():
    result = _run({"degree_discipline_category": "business_mgmt", "code_level": 1, "prior_coursework": ["accounting"],
                   "admission_tests": [{"key": "TOEFL", "score": 85, "test_date": "2025-01-01"}]})
    assert result["verdict"] == "gap" and _hard(result)["english"] == "gap"
    empty = _run({})
    assert empty["verdict"] == "to_confirm"
    assert empty["missing_fields"] == ("degree_discipline_category", "english_medium_degree", "admission_tests")


def test_programming_below_the_bar_is_not_also_listed_as_an_improvement():
    result = _run({"degree_discipline_category": "finance_econ_accounting", "code_level": 0,
                   "english_medium_degree": True})
    assert _hard(result)["programming_or_quant"] == "to_confirm"
    assert "programming_depth" not in result["improvements"] and len(result["improvements"]) <= 2


def test_the_applicant_type_comes_from_work_years_or_graduation_year():
    assert _run({"total_work_years": "3-5"})["applicant_type"] == "experienced"
    assert _run({"bachelor_grad_year": 2026})["applicant_type"] == "fresh_graduate"
    assert _run({})["applicant_type"] == "unknown"


def test_the_same_facts_always_give_the_same_assessment():
    facts = {"degree_discipline_category": "engineering", "prior_coursework": ["linear_algebra", "programming"]}
    assert _run(facts) == _run(facts)
