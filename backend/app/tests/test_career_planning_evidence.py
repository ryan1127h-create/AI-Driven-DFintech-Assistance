"""Exercises career planning's S3 (stages/s3_evidence/skills.py): how
profile facts and courses grade each role skill."""

from __future__ import annotations

import pytest

from app.domains.specialist.career_planning.models import CourseLink, FunctionExperience, StudentEvidence
from app.domains.specialist.career_planning.stages.s3_evidence import skills

LINKS = (
    CourseLink("FT5005", "Machine Learning in Finance", frozenset({"machine_learning_ai", "data_analytics"})),
    CourseLink("IT5001X", "Software Development Fundamentals", frozenset({"software_engineering"})),
    CourseLink("BMD5302", "Financial Modeling", frozenset({"quantitative_finance", "finance_investment"})),
)


def _grade(skill, links=LINKS, **kwargs):
    return skills.assess_skill(skill, StudentEvidence(**kwargs), skills.course_tags(links))


def test_an_empty_profile_leaves_every_skill_unknown():
    graded = skills.assess_skills(StudentEvidence(), LINKS)
    assert set(graded) == set(skills.rules.SKILLS)
    assert {a.status for a in graded.values()} == {"unknown"}
    assert not skills.has_any_evidence(graded)


@pytest.mark.parametrize("facts, status, points", [
    ({"code_level": 3}, "met", 1.0),
    ({"code_level": 4}, "met", 1.0),
    ({"code_level": 2}, "partial", 0.4),
    ({"code_level": 1}, "partial", 0.2),
    ({"code_level": 0}, "missing", 0.0),
])
def test_programming_follows_the_code_level_anchors(facts, status, points):
    graded = _grade("programming", facts=facts)
    assert (graded.status, graded.points) == (status, points)


def test_three_moderate_signals_from_different_fields_meet_a_skill():
    graded = _grade("programming", facts={
        "code_level": 2, "tech_stack": ("python", "sql"), "degree_discipline_category": "cs_se",
    })
    assert graded.status == "met" and graded.points == 1.0
    assert {i.source for i in graded.evidence} == {"code_level", "tech_stack", "degree_discipline_category"}


def test_two_moderate_signals_stay_partial():
    graded = _grade("data_analytics", facts={"tech_stack": ("sql",), "math_stats_level": 2})
    assert (graded.status, graded.points) == ("partial", 0.8)


def test_explicit_absence_gives_way_to_any_other_evidence():
    graded = _grade("programming", facts={"code_level": 0, "tech_stack": ("python",)})
    assert graded.status == "partial"


def test_a_field_counts_once_per_skill():
    # python and java both match the same tech_stack signal: one item, 0.4.
    graded = _grade("programming", facts={"tech_stack": ("python", "java", "excel_vba")})
    assert graded.points == 0.4
    (item,) = graded.evidence
    assert item.values == ("python", "java")


def test_work_experience_is_strong_and_internship_only_counts_half():
    work = _grade("ai_ml", functions=(FunctionExperience("data_ai"),))
    intern = _grade("ai_ml", functions=(FunctionExperience("data_ai", internship=True),))
    assert (work.status, work.points) == ("met", 1.0)
    assert (intern.status, intern.points) == ("partial", 0.5) and intern.evidence[0].internship


def test_work_experience_wins_over_an_internship_in_the_same_line():
    graded = _grade("ai_ml", functions=(
        FunctionExperience("data_ai", internship=True), FunctionExperience("data_ai"),
    ))
    assert graded.points == 1.0 and not graded.evidence[0].internship


def test_courses_count_by_their_role_tags():
    done = _grade("ai_ml", completed_courses=("FT5005",))
    taking = _grade("ai_ml", current_courses=("FT5005",))
    assert done.evidence[0].values == ("FT5005",) and done.points == 0.4
    assert taking.points == 0.2 and taking.evidence[0].in_progress


def test_completed_courses_take_precedence_over_current_ones():
    graded = _grade("finance", completed_courses=("BMD5302",), current_courses=("BMD5302",))
    assert graded.points == 0.4 and not graded.evidence[0].in_progress


def test_a_course_without_a_matching_tag_is_not_evidence():
    assert _grade("security", completed_courses=("FT5005", "UNKNOWN1")).status == "unknown"


def test_a_strong_signal_for_one_skill_is_moderate_for_another():
    functions = (FunctionExperience("quant"),)
    assert _grade("risk_modeling", functions=functions).status == "met"
    assert _grade("finance", functions=functions).status == "partial"


def test_evidence_is_listed_strongest_first():
    graded = _grade("finance", facts={"finance_level": 1, "certifications": ("cfa",)})
    assert [i.source for i in graded.evidence] == ["certifications", "finance_level"]
    assert graded.points == 1.0


def test_single_valued_and_list_facts_both_match():
    assert _grade("product", facts={"degree_discipline_category": "business_mgmt"}).points == 0.4
    assert _grade("payments_systems", facts={"domain_knowledge": ("payments", "digital_assets")}).evidence[0].values \
        == ("payments", "digital_assets")
