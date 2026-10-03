"""profile/validation.py: which fields are shown and editable, value
validation/normalization per value_type, and admission-test expiry."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.profile.validation import (
    FieldValueError,
    drop_expired_items,
    is_displayed,
    lock_reason,
    validate_value,
)
from app.tests.profile_fixtures import DEFINITIONS, ROLE_TAGS, entry

TAGS = set(ROLE_TAGS)


def check(key, value):
    return validate_value(key, value, DEFINITIONS, TAGS)


# --- visibility / editability -----------------------------------------------

@pytest.mark.parametrize("key, shown", [
    ("code_level", True),
    ("application_record", True),
    ("sub_stage", True),
    ("academic_standing", False),  # user_visible = false
    ("drop_off_risk", False),       # derived
    ("motivation_segment", False),  # derived, even though user_visible
    ("language_pref", False),       # account setting
    ("consent_personalized_rec", False),
])
def test_is_displayed(key, shown):
    assert is_displayed(DEFINITIONS[key]) is shown


def test_self_reported_and_cv_fields_are_editable():
    assert lock_reason(DEFINITIONS["code_level"], None) is None
    assert lock_reason(DEFINITIONS["code_level"], entry(2, "CV")) is None
    # CV-only by the dictionary, but users may correct it
    assert lock_reason(DEFINITIONS["degree_discipline_category"], entry("cs_se", "CV")) is None


def test_lifecycle_stage_is_never_user_editable():
    assert lock_reason(DEFINITIONS["lifecycle_stage"], None)
    assert lock_reason(DEFINITIONS["lifecycle_stage"], entry("prospect"))


def test_school_record_values_are_read_only():
    assert lock_reason(DEFINITIONS["study_mode"], None) is None
    assert lock_reason(DEFINITIONS["study_mode"], entry("part_time", "QA")) is None
    assert lock_reason(DEFINITIONS["study_mode"], entry("full_time", "DB")) == "from school records"
    assert lock_reason(DEFINITIONS["current_modules"], entry([], "DB")) == "from school records"


def test_system_fields_are_read_only():
    assert lock_reason(DEFINITIONS["sub_stage"], None) == "maintained by the system"
    assert lock_reason(DEFINITIONS["drop_off_risk"], None)


# --- values -----------------------------------------------------------------

def test_single_choice_and_numeric_enum_coercion():
    assert check("seniority_level", "junior") == "junior"
    assert check("code_level", 3) == 3
    assert check("code_level", "3") == 3  # from a form select
    for bad in (7, "expert", True):
        with pytest.raises(FieldValueError):
            check("code_level", bad)


def test_multi_checks_allowed_values_duplicates_and_max_items():
    assert check("target_markets", ["SG", "US"]) == ["SG", "US"]
    with pytest.raises(FieldValueError, match="not an allowed value"):
        check("target_markets", ["MARS"])
    with pytest.raises(FieldValueError, match="twice"):
        check("target_markets", ["SG", "SG"])
    with pytest.raises(FieldValueError, match="at most 3"):
        check("decision_factors", ["cost", "duration", "tech_depth", "scholarship"])
    with pytest.raises(FieldValueError, match="expects a list"):
        check("target_markets", "SG")


def test_role_tags_come_from_the_tag_table():
    assert check("target_role_families", ["blockchain"]) == ["blockchain"]
    with pytest.raises(FieldValueError, match="role tag"):
        check("target_role_families", ["astrology"])


def test_multi_item_attributes():
    assert check("languages", [{"key": "zh", "level": "fluent"}, {"key": "en"}]) == [
        {"key": "zh", "level": "fluent"}, {"key": "en"}]
    with pytest.raises(FieldValueError):
        check("languages", [{"key": "zh", "level": "native"}])
    with pytest.raises(FieldValueError, match="unexpected"):
        check("certifications", [{"key": "cfa", "score": 1}])
    assert check("certifications", [{"key": "cfa", "level": " L2 "}]) == [{"key": "cfa", "level": "L2"}]


def test_free_text_items_are_capped():
    assert check("competing_programs", ["NTU MSc FinTech"]) == ["NTU MSc FinTech"]
    with pytest.raises(FieldValueError, match="longer"):
        check("competing_programs", ["x" * 121])


def test_scalar_types():
    assert check("is_nus_alumnus", False) is False
    with pytest.raises(FieldValueError):
        check("is_nus_alumnus", "no")
    assert check("bachelor_grad_year", "2021") == 2021
    with pytest.raises(FieldValueError):
        check("bachelor_grad_year", 1800)
    assert check("intake_term", "AY2027/28 Sem1") == "AY2027/28 Sem1"
    with pytest.raises(FieldValueError, match="term like"):
        check("intake_term", "Fall 2027")


def test_admission_tests():
    assert check("admission_tests", [
        {"key": "GRE", "score": "325", "test_date": "2025-03-01"},
        {"key": "IELTS", "score": 7.5},
    ]) == [{"key": "GRE", "score": 325, "test_date": "2025-03-01"}, {"key": "IELTS", "score": 7.5}]
    for bad in ([{"key": "SAT", "score": 1}], [{"key": "GRE", "score": -1}],
                [{"key": "GRE", "score": 320, "test_date": "2025-02-30"}], [{"key": "GRE", "rank": 1}]):
        with pytest.raises(FieldValueError):
            check("admission_tests", bad)


def test_structured_objects():
    assert check("current_position", {"role_family": "data_analytics", "region": "SG", "seniority": "junior"}) == {
        "role_family": "data_analytics", "region": "SG", "seniority": "junior"}
    assert check("currently_hiring", {"hiring": True, "role_families": ["blockchain"]}) == {
        "hiring": True, "role_families": ["blockchain"]}
    with pytest.raises(FieldValueError):
        check("current_position", {"role_family": "astrology"})
    with pytest.raises(FieldValueError, match="unexpected"):
        check("currently_hiring", {"hiring": True, "salary": 1})


def test_non_writable_types_are_rejected():
    with pytest.raises(FieldValueError):
        check("current_modules", [])
    with pytest.raises(FieldValueError, match="unknown"):
        check("nonexistent", 1)


# --- expiry -----------------------------------------------------------------

def test_expired_tests_are_dropped():
    tests = [
        {"key": "GRE", "score": 320, "test_date": "2021-10-01"},    # 5y -> valid until 2026-10-01
        {"key": "IELTS", "score": 7, "test_date": "2024-01-01"},    # 2y -> expired 2026-01-01
        {"key": "TOEFL", "score": 100},                              # no date: kept
    ]
    kept = drop_expired_items(tests, DEFINITIONS["admission_tests"], date(2026, 9, 28))
    assert [t["key"] for t in kept] == ["GRE", "TOEFL"]
    assert drop_expired_items(["SG"], DEFINITIONS["target_markets"], date(2026, 9, 28)) == ["SG"]
