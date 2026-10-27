"""Exercises career planning's S4 (stages/s4_fit/roles.py): role fit from
graded skills, the experience bonus, low confidence, course support and
the ranking."""

from __future__ import annotations

from app.domains.specialist.career_planning.models import (
    CourseLink,
    FunctionExperience,
    RoleDefinition,
    SkillAssessment,
    StudentEvidence,
)
from app.domains.specialist.career_planning.policy import skill_evidence, tuning
from app.domains.specialist.career_planning.stages.s4_fit import roles

DA = RoleDefinition("data_analytics", "Data Analytics", "", ("data_analytics", "programming", "finance"))
QF = RoleDefinition("quantitative_finance", "Quantitative Finance", "",
                    ("programming", "finance", "risk_modeling", "data_analytics"))
SEC = RoleDefinition("cybersecurity", "Cybersecurity", "", ("security", "programming", "regulation"))

LINKS = (
    CourseLink("FT5005", "ML in Finance", frozenset({"data_analytics"})),
    CourseLink("FT5006", "Analytics", frozenset({"data_analytics", "quantitative_finance"})),
    CourseLink("IT5006", "Security", frozenset({"cybersecurity"})),
)

_STATUS_POINTS = {"met": 1.0, "partial": 0.4, "missing": 0.0, "unknown": 0.0}


def _graded(**statuses):
    result = {s: SkillAssessment(s, "unknown", 0.0, ()) for s in skill_evidence.SKILLS}
    for skill, status in statuses.items():
        result[skill] = SkillAssessment(skill, status, _STATUS_POINTS[status], ())
    return result


def test_fit_is_the_mean_evidence_over_the_roles_skills():
    fit = roles.fit_role(DA, _graded(data_analytics="met", programming="partial", finance="missing"),
                         StudentEvidence(), LINKS)
    assert fit.fit == round((1.0 + 0.4 + 0.0) / 3, 3)
    assert (fit.met_skills, fit.partial_skills, fit.missing_skills) == (("data_analytics",), ("programming",), ("finance",))
    assert fit.unknown_share == 0 and not fit.low_confidence


def test_mostly_unknown_skills_make_a_fit_low_confidence():
    fit = roles.fit_role(QF, _graded(programming="met"), StudentEvidence(), LINKS)
    assert fit.unknown_share == 0.75 and fit.low_confidence
    assert fit.unknown_skills == ("finance", "risk_modeling", "data_analytics")


def test_work_in_the_roles_line_adds_a_bonus_internship_half():
    graded = _graded(data_analytics="partial")
    work = roles.fit_role(DA, graded, StudentEvidence(functions=(FunctionExperience("data_ai"),)), LINKS)
    intern = roles.fit_role(DA, graded, StudentEvidence(functions=(FunctionExperience("data_ai", True),)), LINKS)
    none = roles.fit_role(DA, graded, StudentEvidence(functions=(FunctionExperience("sales_client"),)), LINKS)
    assert work.fit == round(none.fit + tuning.FUNCTION_AFFINITY_BONUS, 3) and work.experience == ("data_ai",)
    assert intern.fit == round(none.fit + tuning.FUNCTION_AFFINITY_BONUS / 2, 3)
    assert none.experience == ()


def test_fit_is_capped_at_one():
    graded = _graded(data_analytics="met", programming="met", finance="met")
    fit = roles.fit_role(DA, graded, StudentEvidence(functions=(FunctionExperience("data_ai"),)), LINKS)
    assert fit.fit == 1.0


def test_the_experience_bonus_never_makes_a_role_with_a_gap_a_full_fit():
    graded = _graded(data_analytics="met", programming="partial", finance="met")
    fit = roles.fit_role(DA, graded, StudentEvidence(functions=(FunctionExperience("data_ai"),)), LINKS)
    assert fit.fit == tuning.FIT_CAP_WITH_GAPS  # 0.8 + 0.15 would be 0.95


def test_course_support_lists_the_roles_courses_and_the_students_share():
    evidence = StudentEvidence(completed_courses=("FT5005", "IT5006"), current_courses=("FT5006",))
    support = roles.fit_role(DA, _graded(), evidence, LINKS).support
    assert support.course_codes == ("FT5005", "FT5006")
    assert support.taken == ("FT5005",) and support.taking == ("FT5006",)


def test_ranking_puts_the_best_fit_first_and_breaks_ties_on_evidence():
    graded = _graded(programming="met", data_analytics="met", finance="partial")
    ranked = roles.rank_roles((SEC, QF, DA), graded, StudentEvidence(), LINKS, preferred=frozenset({"cybersecurity"}))
    assert [f.role.tag for f in ranked] == ["data_analytics", "quantitative_finance", "cybersecurity"]
    assert ranked[2].preferred


def test_equal_fits_prefer_the_role_the_student_lists():
    a = RoleDefinition("a_role", "A", "", ("programming",))
    b = RoleDefinition("b_role", "B", "", ("programming",))
    ranked = roles.rank_roles((a, b), _graded(programming="met"), StudentEvidence(), (), frozenset({"b_role"}))
    assert [f.role.tag for f in ranked] == ["b_role", "a_role"]
