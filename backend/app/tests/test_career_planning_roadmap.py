"""Exercises career planning's S5 (stages/s5_roadmap/): the anchors a
roadmap hangs on and the dated phases it lays the gaps onto. Every date
follows from a fixed "today"."""

from __future__ import annotations

from datetime import date

from app.domains.specialist.career_planning.models import ReadinessGap, RoadmapContext, SkillAssessment
from app.domains.specialist.career_planning.stages.s5_roadmap import anchors, planner

TODAY = date(2026, 10, 13)


def _skill(skill, status, points=0.0):
    return SkillAssessment(skill, status, points, ())


GAPS = (
    _skill("programming", "met", 1.0),
    _skill("finance", "partial", 0.4),
    _skill("risk_modeling", "missing"),
    _skill("data_analytics", "unknown"),
)


def _ctx(**kwargs):
    return RoadmapContext(today=kwargs.pop("today", TODAY), **kwargs)


def _kinds(roadmap):
    return [p.kind for p in roadmap.phases]


def _actions(roadmap):
    return [a for p in roadmap.phases for a in p.actions]


# --- anchors ---

def test_a_current_student_graduating_dec_2027_does_the_2027_capstone():
    a = anchors.resolve(_ctx(stage="current", expected_grad_term="AY2027/28 Sem1"))
    assert not a.pre_programme and a.cycle.year == 2027 and a.cycle.projected
    assert a.graduation.label == "AY2027/28 Sem1" and not a.graduation_estimated


def test_a_prospect_starts_next_august_and_graduation_is_estimated():
    a = anchors.resolve(_ctx(stage="prospect"))
    assert a.pre_programme and a.programme_start == date(2027, 8, 1)
    assert a.cycle.year == 2028 and a.graduation.label == "AY2028/29 Sem1" and a.graduation_estimated


def test_an_admitted_student_before_august_starts_this_year():
    a = anchors.resolve(_ctx(stage="admitted", today=date(2027, 3, 1)))
    assert a.programme_start == date(2027, 8, 1) and a.cycle.year == 2028


def test_an_admitted_student_after_august_has_already_started():
    a = anchors.resolve(_ctx(stage="admitted"))
    assert not a.pre_programme and a.programme_start is None


def test_without_a_graduation_term_a_current_student_takes_the_next_open_cycle():
    a = anchors.resolve(_ctx(stage="current"))
    assert a.cycle.year == 2027 and a.graduation.label == "AY2027/28 Sem1" and a.graduation_estimated


# --- phases ---

def test_a_current_students_roadmap_runs_from_build_up_through_job_search():
    roadmap = planner.build_roadmap(_ctx(stage="current", expected_grad_term="AY2027/28 Sem1"), GAPS)
    assert _kinds(roadmap) == ["build_up", "capstone_applications", "capstone_internship", "job_search"]
    build_up, applications, internship, search = roadmap.phases
    assert (build_up.start, build_up.end) == (TODAY, date(2026, 11, 30))
    assert (applications.start, applications.end) == (date(2026, 12, 1), date(2027, 3, 31))
    assert [m.kind for m in applications.milestones] == [
        "capstone_applications_open", "capstone_applications_close", "capstone_offers_by"]
    assert all(m.projected for m in applications.milestones)
    assert (internship.start, internship.end) == (date(2027, 5, 18), date(2027, 10, 16))
    # Right after graduating (the default): 4 months before the term ends, 3 after.
    assert (search.start, search.end) == (date(2027, 9, 1), date(2028, 3, 31))
    assert search.milestones[0].kind == "graduation"
    assert roadmap.capstone_cycle_year == 2027
    assert any("2027 Capstone dates" in n for n in roadmap.notes)


def test_gaps_come_missing_first_and_unknown_skills_ask_for_evidence():
    roadmap = planner.build_roadmap(_ctx(stage="current", expected_grad_term="AY2027/28 Sem1"), GAPS)
    first = roadmap.phases[0].actions
    assert [a.kind for a in first] == ["evidence", "skill", "skill"]
    assert first[0].subjects == ("data_analytics",)
    assert [a.subjects for a in first[1:]] == [("risk_modeling",), ("finance",)]
    assert not any(a.subjects == ("programming",) for a in _actions(roadmap))   # met: nothing to do


def test_a_prospects_roadmap_starts_with_readiness_before_the_programme():
    roadmap = planner.build_roadmap(
        _ctx(stage="prospect"), GAPS, (ReadinessGap("maths_stats", 1, 2),))
    assert _kinds(roadmap)[0] == "before_programme"
    before = roadmap.phases[0]
    assert before.end == date(2027, 7, 31) and before.milestones[0].on == date(2027, 8, 1)
    assert before.actions[0].kind == "readiness" and "level 2" in before.actions[0].text
    assert any("assumes full-time study ending AY2028/29 Sem1" in n for n in roadmap.notes)


def test_readiness_gaps_are_left_out_once_in_the_programme():
    roadmap = planner.build_roadmap(
        _ctx(stage="current", expected_grad_term="AY2027/28 Sem1"), GAPS, (ReadinessGap("finance", 0, 1),))
    assert not any(a.kind == "readiness" for a in _actions(roadmap))


def test_a_secured_internship_skips_the_applications():
    roadmap = planner.build_roadmap(
        _ctx(stage="current", expected_grad_term="AY2027/28 Sem1", internship_status="secured"), GAPS)
    assert "capstone_applications" not in _kinds(roadmap) and "capstone_internship" in _kinds(roadmap)


def test_once_applications_close_an_internship_is_only_planned_if_secured():
    today = date(2027, 4, 20)
    unsure = planner.build_roadmap(_ctx(stage="current", expected_grad_term="AY2027/28 Sem1", today=today), GAPS)
    secured = planner.build_roadmap(_ctx(stage="current", expected_grad_term="AY2027/28 Sem1", today=today,
                                         internship_status="secured"), GAPS)
    assert _kinds(unsure) == ["job_search"]
    assert _kinds(secured) == ["capstone_internship", "job_search"]
    assert secured.phases[0].start == date(2027, 5, 18)


def test_gaps_left_over_join_the_first_phase():
    roadmap = planner.build_roadmap(
        _ctx(stage="graduating", expected_grad_term="AY2026/27 Sem1", internship_status="completed"), GAPS)
    assert _kinds(roadmap) == ["job_search"]
    assert {a.kind for a in roadmap.phases[0].actions} == {"job_search", "skill", "evidence"}
    assert roadmap.phases[0].start == TODAY
    assert any("Capstone internship is completed" in n for n in roadmap.notes)


def test_electives_instead_of_the_capstone_means_no_internship_phases():
    roadmap = planner.build_roadmap(
        _ctx(stage="current", expected_grad_term="AY2027/28 Sem1", capstone_intent="electives_instead"), GAPS)
    assert _kinds(roadmap) == ["job_search"] and roadmap.capstone_cycle_year is None
    assert any("electives instead" in n for n in roadmap.notes)


def test_job_search_timelines():
    base = {"stage": "current", "expected_grad_term": "AY2027/28 Sem1"}
    during = planner.build_roadmap(_ctx(job_search_timeline="during_program", **base), GAPS)
    later = planner.build_roadmap(_ctx(job_search_timeline="1yr_plus_later", **base), GAPS)
    none = planner.build_roadmap(_ctx(job_search_timeline="not_job_seeking", **base), GAPS)
    search = next(p for p in during.phases if p.kind == "job_search")
    assert (search.kind, search.start, search.end) == ("job_search", TODAY, date(2027, 12, 31))
    assert any("Student's Pass" in n for n in during.notes)
    assert "job_search" not in _kinds(later) and any("a year or more" in n for n in later.notes)
    assert "job_search" not in _kinds(none) and any("aren't looking" in n for n in none.notes)


def test_market_notes():
    base = {"stage": "current", "expected_grad_term": "AY2027/28 Sem1"}
    abroad = planner.build_roadmap(_ctx(target_markets=("CN", "HK"), **base), GAPS)
    home = planner.build_roadmap(_ctx(target_markets=("SG",), **base), GAPS)
    anywhere = planner.build_roadmap(_ctx(target_markets=("ANY", "CN"), **base), GAPS)
    assert any("must be located in Singapore" in n for n in abroad.notes)
    assert any("no job-market data for CN, HK" in n for n in abroad.notes)
    assert not [n for n in home.notes if "Singapore" in n or "market" in n]
    assert not [n for n in anywhere.notes if "market" in n]


def test_phases_are_in_date_order_and_never_start_before_today():
    for stage, term in (("prospect", None), ("current", "AY2027/28 Sem1"), ("graduating", "AY2026/27 Sem2")):
        roadmap = planner.build_roadmap(_ctx(stage=stage, expected_grad_term=term), GAPS)
        starts = [p.start for p in roadmap.phases]
        assert starts == sorted(starts) and min(starts) >= TODAY
        assert all(p.start <= p.end for p in roadmap.phases)
