"""program_comparison/contracts.py: the report the tools layer hands the
domain — one MSc DFT baseline, subjects that exist and fit the mode,
catalogue rows that are internally consistent."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.specialist.program_comparison.contracts import AdmissionTestInput, ComparisonInput


def program(pid: str, *, is_target: bool = False, **extra) -> dict:
    return {
        "program_id": pid, "name": pid, "short_name": pid, "degree_type": "MSc", "category": "fintech",
        "is_target": is_target, "official_url": "https://example.edu", "intake_year": 2027,
        "university": {"university_id": "nus" if is_target else "hkust", "name": "U", "short_name": "U",
                       "city": "C", "country_code": "SG" if is_target else "HK", "country_name": "X"},
        **extra,
    }


def report(mode="compare", subjects=("ust",), **extra) -> dict:
    return {"mode": mode, "today": date(2026, 10, 14), "subject_ids": list(subjects),
            "programs": [program("dft", is_target=True), program("ust"), program("ntu")], **extra}


def test_a_comparison_is_dft_against_named_programmes():
    validated = ComparisonInput.model_validate(report(subjects=("ust", "ntu")))
    assert validated.subject_ids == ["ust", "ntu"]


@pytest.mark.parametrize("mode, subjects", [
    ("compare", ()),                  # nothing to compare against
    ("compare", ("dft",)),            # DFT is the baseline, not a subject
    ("compare", ("ust", "x")),        # not in the catalogue
    ("detail", ("ust", "ntu")),       # one programme only
    ("explore", ("ust",)),            # explore takes no subjects
])
def test_subjects_must_fit_the_mode(mode, subjects):
    with pytest.raises(ValidationError):
        ComparisonInput.model_validate(report(mode, subjects))


def test_detail_may_be_about_dft_itself():
    assert ComparisonInput.model_validate(report("detail", ("dft",))).mode == "detail"


def test_exactly_one_target_programme():
    data = report()
    data["programs"][1]["is_target"] = True
    with pytest.raises(ValidationError):
        ComparisonInput.model_validate(data)


def test_a_programme_cannot_list_a_skill_twice():
    data = report()
    data["programs"][1]["curriculum"] = [
        {"skill_id": "finance", "coverage": "required", "evidence_courses": ["A"]},
        {"skill_id": "finance", "coverage": "elective", "evidence_courses": ["B"]},
    ]
    with pytest.raises(ValidationError):
        ComparisonInput.model_validate(data)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ComparisonInput.model_validate(report(ranking=["ust"]))


def test_test_scores_read_dates():
    assert AdmissionTestInput.model_validate({"key": "IELTS", "score": 6.5, "test_date": "2024-10-20"}).test_date == date(2024, 10, 20)
