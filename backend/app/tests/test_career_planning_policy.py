"""Exercises career planning's input contract and policy tables: what a
valid report is, that every evidence signal reads a field the contract
carries, and the semester and Capstone dates the roadmap is built on."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.specialist.career_planning.contracts import CareerPlanningInput, ProfileEvidenceInput
from app.domains.specialist.career_planning.policy import calendar, skill_evidence, tuning

# knowledge.tags_definition's role tags.
ROLE_TAGS = {
    "blockchain", "cybersecurity", "data_analytics", "data_engineering", "entrepreneurship",
    "finance_investment", "machine_learning_ai", "product_business", "quantitative_finance",
    "regulation_governance", "risk_management", "software_engineering",
}


def _catalog():
    return [
        {"tag": "data_analytics", "name": "Data Analytics", "required_skills": ["data_analytics", "programming"]},
        {"tag": "quantitative_finance", "name": "Quantitative Finance", "required_skills": ["finance", "risk_modeling"]},
        {"tag": "software_engineering", "name": "Software Engineering", "required_skills": ["programming"]},
    ]


def _report(**overrides):
    report = {"mode": "plan", "today": date(2026, 10, 13), "target_roles": ["data_analytics"],
              "role_catalog": _catalog()}
    report.update(overrides)
    return report


# --- contract ---

def test_a_minimal_plan_report_validates():
    request = CareerPlanningInput.model_validate(_report())
    assert request.schema_version == "1.0" and request.profile.code_level is None


@pytest.mark.parametrize("overrides", [
    {"target_roles": []},                                          # a plan needs its role
    {"target_roles": ["data_analytics", "software_engineering"]},  # ...and only one
    {"mode": "compare"},                                           # a comparison needs two
    {"mode": "exploration"},                                       # exploration takes none
    {"target_roles": ["astronaut"]},                               # unknown role
    {"preferred_roles": ["astronaut"]},
    {"course_links": [{"code": "FT5005", "title": "x", "tags": ["astronaut"]}]},
    {"course_links": [{"code": "FT5005", "title": "x", "tags": ["data_analytics"]}] * 2},
    {"situation": {"expected_grad_term": "next year"}},
    {"profile": {"code_level": 5}},
    {"profile": {"completed_courses": ["not a code"]}},
    {"surprise": True},
])
def test_inconsistent_reports_are_rejected(overrides):
    with pytest.raises(ValidationError):
        CareerPlanningInput.model_validate(_report(**overrides))


def test_course_codes_are_normalised_and_deduplicated():
    profile = ProfileEvidenceInput(completed_courses=["ft5005", "FT5005", "it5001x"])
    assert profile.completed_courses == ["FT5005", "IT5001X"]


def test_compare_and_exploration_reports_validate():
    CareerPlanningInput.model_validate(
        _report(mode="compare", target_roles=["data_analytics", "quantitative_finance"]))
    CareerPlanningInput.model_validate(_report(mode="exploration", target_roles=[], preferred_roles=["data_analytics"]))


# --- skill evidence table ---

def test_every_skill_has_signals_and_every_signal_reads_a_contract_field():
    assert set(skill_evidence.SKILL_SIGNALS) == set(skill_evidence.SKILLS)
    assert skill_evidence.EVIDENCE_FIELDS <= set(ProfileEvidenceInput.model_fields)


def test_course_signals_name_real_role_tags():
    for signals in skill_evidence.SKILL_SIGNALS.values():
        for signal in signals:
            if signal.kind == "course_tag":
                assert signal.values <= ROLE_TAGS


def test_only_a_strong_signal_meets_a_skill_on_its_own():
    for signals in skill_evidence.SKILL_SIGNALS.values():
        for signal in signals:
            points = [p for _, p in signal.levels] if signal.kind == "level" else [signal.points]
            for p in points:
                assert p == skill_evidence.STRONG or p < skill_evidence.MET_POINTS


def test_function_affinity_names_real_role_tags():
    for roles in tuning.FUNCTION_ROLE_AFFINITY.values():
        assert roles <= ROLE_TAGS


# --- calendar ---

def test_terms_round_trip_with_the_student_record():
    term = calendar.parse_term("AY2027/28 Sem1")
    assert term == calendar.Term(2027, 1) and term.label == "AY2027/28 Sem1"
    assert term.start == date(2027, 8, 1) and term.end == date(2027, 12, 31)
    assert calendar.Term(2027, 2).end == date(2028, 5, 31)
    assert term.following() == calendar.Term(2027, 2)
    assert calendar.parse_term("AY2027/29 Sem1") is None and calendar.parse_term(None) is None


def test_the_reference_cycle_is_the_capstone_pages_dates():
    cycle = calendar.capstone_cycle(2027)
    assert not cycle.projected
    assert cycle.applications_open == date(2026, 12, 1) and cycle.applications_close == date(2027, 3, 31)
    assert cycle.offers_by == date(2027, 4, 15)
    assert (cycle.internship_start, cycle.internship_end) == (date(2027, 5, 17), date(2027, 10, 15))
    assert calendar.capstone_cycle(2028).projected


@pytest.mark.parametrize("today, year", [
    (date(2026, 10, 13), 2027),   # the 2026 cycle's applications closed in March
    (date(2026, 3, 31), 2026),
    (date(2026, 4, 1), 2027),
    (date(2026, 12, 20), 2027),   # applications for 2027 are open
])
def test_next_open_cycle(today, year):
    assert calendar.next_open_cycle(today).year == year


@pytest.mark.parametrize("graduation, year", [
    ("AY2027/28 Sem1", 2027),   # graduating Dec 2027: the May-Oct 2027 internship
    ("AY2027/28 Sem2", 2027),   # graduating May 2028: still the 2027 one
    ("AY2026/27 Sem1", 2026),
])
def test_cycle_before_graduation(graduation, year):
    assert calendar.cycle_before_graduation(calendar.parse_term(graduation)).year == year
