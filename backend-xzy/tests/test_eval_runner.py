"""Tests for eval.runner — single-case evaluation over the real rule engines.

Gold expectations are derived independently from the admissions rules / role
skill map (not copied from engine output), so a regression in the engine shows
up as a failing case.
"""
from __future__ import annotations

from eval.runner import evaluate_case

# 7 mandatory base documents (required != false in admissions_rules.json).
_REQUIRED_BASE = [
    "personal_statement", "cv", "proof_of_residence", "degree_certificate",
    "transcript", "referee_reports", "application_fee",
]


def test_checklist_exempt_country_excludes_english():
    # profile 2: country=SG -> English proof NOT required.
    case = {
        "id": "chk_sg",
        "agent": "checklist",
        "profile_ref": "2",
        "expect": {
            "must_include": _REQUIRED_BASE,
            "must_exclude": ["english_proficiency"],
        },
    }
    r = evaluate_case(case)
    assert r.passed
    assert r.metrics["include_recall"] == 1.0
    assert r.metrics["exclude_ok"] == 1.0


def test_checklist_nonexempt_country_includes_english():
    # profile 1: country=IN -> English proof required.
    case = {
        "id": "chk_in",
        "agent": "checklist",
        "profile_ref": "1",
        "expect": {
            "must_include": _REQUIRED_BASE + ["english_proficiency"],
            "status": {"cv": "submitted", "transcript": "missing"},
        },
    }
    r = evaluate_case(case)
    assert r.passed
    assert r.metrics["include_recall"] == 1.0
    assert r.metrics["status_accuracy"] == 1.0


def test_checklist_wrong_gold_fails_and_reports():
    # Deliberately wrong gold: claim English is required for SG. Engine excludes
    # it, so the case must FAIL and surface the violation.
    case = {
        "id": "chk_bad",
        "agent": "checklist",
        "profile_ref": "2",
        "expect": {"must_include": ["english_proficiency"]},
    }
    r = evaluate_case(case)
    assert not r.passed
    assert r.metrics["include_recall"] < 1.0
    assert any("english_proficiency" in d for d in r.details)


def test_navigator_gap_for_junior_pm():
    # profile 1: have {programming, data_analytics, finance};
    # fintech_pm requires {product, finance, data_analytics, programming}.
    case = {
        "id": "nav_p1_pm",
        "agent": "navigator",
        "profile_ref": "1",
        "role": "fintech_pm",
        "expect": {"skill_gaps": ["product"]},
    }
    r = evaluate_case(case)
    assert r.passed
    assert r.metrics["gap_f1"] == 1.0


def test_navigator_no_gap_for_senior_fintech():
    # profile 5: senior fintech, advanced tech -> covers all fintech_pm skills.
    case = {
        "id": "nav_p5_pm",
        "agent": "navigator",
        "profile_ref": "5",
        "role": "fintech_pm",
        "expect": {"skill_gaps": []},
    }
    r = evaluate_case(case)
    assert r.passed
    assert r.metrics["gap_f1"] == 1.0
