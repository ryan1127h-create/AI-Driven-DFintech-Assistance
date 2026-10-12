"""Exercises S6's semester_plan: the unit budget, the planner's choice
(remaining mandatory courses first, then the best combination that fills
the budget within each requirement's need, corequisites paired, the
Capstone counting 6 units), unavoidable clashes flagged not dropped,
alternatives, and the plan end to end with its projected progress."""

from __future__ import annotations

from app.domains.specialist.course_recommendation import interface
from app.domains.specialist.course_recommendation.models import (
    Course, Pick, PlanContext, PlanPool, PlanTerm, ScoredCourse, Session,
)
from app.domains.specialist.course_recommendation.stages.s6_modes.semester_plan.budget import unit_budget
from app.domains.specialist.course_recommendation.stages.s6_modes.semester_plan.planner import search

TERM = PlanTerm("2026-2027", 2, "AY2026/27 Sem2")


def _ctx(**kw) -> PlanContext:
    defaults = dict(term=TERM, requested_units=None, study_mode="full_time", units_remaining=36,
                    level4000_allowance=2, done=frozenset())
    defaults.update(kw)
    return PlanContext(**defaults)


def _pick(code: str, score: float = 0.0, units: int = 4, slot=None, day="Monday", start="09:00", end="12:00",
          level: int = 5000, coreq: tuple[str, ...] = ()) -> Pick:
    course = Course(code=code, title=code, units=units, section="", skills=(), description="",
                    prerequisite_text="", preclusion_text="", can_recommend=True, source_url="", level=level,
                    corequisite_codes=coreq,
                    sessions=(Session("2026-2027", 2, "Lecture", "1", day, start, end),))
    return Pick(ScoredCourse(course, score, (), (), (), False), reason="", slot=slot)


def _pool(kind: str, quota: int, *picks: Pick) -> PlanPool:
    return PlanPool(kind=kind, label=kind, quota=quota, picks=picks)


# ---- budget -------------------------------------------------------------------

def test_the_default_load_follows_the_study_mode():
    assert unit_budget(None, "full_time", 36).units == 16
    assert unit_budget(None, "part_time", 36).units == 8


def test_a_requested_load_is_kept_within_the_programmes_limits():
    over = unit_budget(24, "full_time", 36)
    assert over.units == 20 and over.source == "requested" and "at most 20 units" in over.notes[0]
    under = unit_budget(8, "full_time", 36)
    assert under.units == 8 and "below the 12-unit minimum" in under.notes[0]


def test_never_more_than_is_left_to_graduate():
    budget = unit_budget(None, "full_time", 8)
    assert budget.units == 8 and "Only 8 units remain" in budget.notes[0]


def test_an_unset_study_mode_is_planned_full_time_and_said():
    budget = unit_budget(None, "undecided", 36)
    assert budget.units == 16 and budget.study_mode == "full_time" and "isn't set" in budget.notes[0]


# ---- planner -------------------------------------------------------------------

def test_mandatory_courses_come_first_then_the_best_fill():
    pools = (
        _pool("core_mandatory", 2, _pick("BMD5302", day="Monday"), _pick("IT5006", day="Tuesday")),
        _pool("elective", 3, _pick("E1", 3.0, day="Wednesday"), _pick("E2", 2.0, day="Thursday"),
              _pick("E3", 1.0, day="Friday")),
    )
    best, _, notes = search(pools, 16, _ctx())
    assert best.codes == {"BMD5302", "IT5006", "E1", "E2"} and best.units == 16 and notes == ()


def test_a_requirement_never_gets_more_than_it_needs():
    pools = (_pool("core_choice", 1, _pick("FT5009", 3.0, day="Monday"), _pick("FT5010", 2.0, day="Tuesday")),
             _pool("elective", 1, _pick("E1", 1.0, day="Wednesday")))
    best, _, notes = search(pools, 16, _ctx())
    assert best.codes == {"FT5009", "E1"} and best.units == 8
    assert "Only 8 of the 16 units could be filled" in notes[0]


def test_a_corequisite_must_be_done_or_in_the_plan():
    capstone = _pick("FT5007", 5.0, units=12, coreq=("IT5006",), day="Saturday")
    pools = (_pool("capstone", 1, capstone), _pool("elective", 3, _pick("E1", 1.0, day="Monday")))
    assert "FT5007" not in search(pools, 16, _ctx())[0].codes
    best = search(pools, 16, _ctx(done=frozenset({"IT5006"})))[0]
    assert "FT5007" in best.codes


def test_the_capstone_counts_six_units_this_semester():
    capstone = _pick("FT5007", 5.0, units=12, day="Saturday")
    pools = (_pool("capstone", 1, capstone),
             _pool("elective", 3, _pick("E1", 1.0, day="Monday"), _pick("E2", 1.0, day="Tuesday")))
    best = search(pools, 14, _ctx())[0]
    assert best.codes == {"FT5007", "E1", "E2"} and best.units == 14  # 6 + 4 + 4


def test_4000_level_electives_stay_within_what_can_count():
    pools = (_pool("elective", 3, _pick("IS4261", 3.0, level=4000, day="Monday"),
                   _pick("IS4262", 3.0, level=4000, day="Tuesday"), _pick("CS5224", 1.0, day="Wednesday")),)
    best = search(pools, 8, _ctx(level4000_allowance=1))[0]
    assert len({"IS4261", "IS4262"} & best.codes) == 1 and "CS5224" in best.codes


def test_an_unavoidable_clash_is_flagged_and_a_clash_free_equal_preferred():
    pools = (_pool("elective", 2, _pick("A", 2.0, day="Monday", start="18:30", end="21:30"),
                   _pick("B", 2.0, day="Monday", start="19:00", end="21:00"),
                   _pick("C", 2.0, day="Tuesday", start="18:30", end="21:30")),)
    best, alternatives, _ = search(pools, 8, _ctx())
    assert best.clashes == () and "C" in best.codes
    clashing, _, _ = search((_pool("elective", 2, *pools[0].picks[:2]),), 8, _ctx())
    assert clashing.clashes == (("A", "B", "Monday 18:30–21:30"),)


def test_alternatives_differ_by_at_least_a_swap():
    pools = (_pool("elective", 2, *(_pick(c, s, day=d) for c, s, d in (
        ("E1", 4.0, "Monday"), ("E2", 3.0, "Tuesday"), ("E3", 2.0, "Wednesday"), ("E4", 1.0, "Thursday")))),)
    best, alternatives, _ = search(pools, 8, _ctx())
    assert best.codes == {"E1", "E2"}
    assert 1 <= len(alternatives) <= 2
    assert all(len(alt.codes ^ best.codes) >= 2 for alt in alternatives)


# ---- end to end -------------------------------------------------------------

def _session(semester: int, day: str, start: str = "18:30", end: str = "21:30") -> list[dict]:
    return [{"ay": "2026-2027", "semester": semester, "lesson_type": "Lecture", "class_no": "1",
             "day": day, "start": start, "end": end}]


def test_a_semester_plan_end_to_end():
    v2 = "Vertical #2. Financial Data Analytics and Intelligence"
    catalog = [
        {"code": "BMD5301", "title": "Finance", "units": 4, "can_recommend": True, "sessions": _session(1, "Monday")},
        {"code": "IT5001X", "title": "Programming", "units": 4, "can_recommend": True, "sessions": _session(1, "Tuesday")},
        {"code": "BMD5302", "title": "Modelling", "units": 4, "can_recommend": True, "sessions": _session(2, "Monday")},
        {"code": "IT5006", "title": "Data Analytics", "units": 4, "can_recommend": True, "sessions": _session(2, "Thursday"),
         "prerequisites": {"all_of": [["IT5001", "IT5001X"]]}},
        {"code": "FT5009", "title": "Financial Data", "units": 4, "can_recommend": True, "sessions": _session(1, "Friday")},
        {"code": "FT5010", "title": "Algo Trading", "units": 4, "can_recommend": True, "sessions": _session(2, "Wednesday")},
        {"code": "CS5242", "title": "Neural Networks", "units": 4, "can_recommend": True, "vertical": [v2],
         "sessions": _session(2, "Monday", "19:00", "21:00")},
    ]
    result = interface.recommend_courses({
        "course_catalog": catalog, "mode": "semester_plan",
        "background": {"completed_courses": ["BMD5301", "IT5001X"]},
        "student": {"study_mode": "full_time"},
        "planning": {"ay": "2026-2027", "semester": 2, "label": "AY2026/27 Sem2", "requested_units": 16},
    })
    plan = result["plan"]
    assert result["mode"] == "semester_plan"
    assert plan["unit_budget"] == 16 and plan["units"] == 16 and plan["budget_source"] == "requested"
    assert set(plan["courses"]) == {"BMD5302", "IT5006", "FT5010", "CS5242"}  # FT5009 doesn't run in Sem 2
    assert plan["clashes"] == [{"courses": ["BMD5302", "CS5242"], "when": "Monday 18:30–21:30"}]
    projected = plan["projected_progress"]
    assert projected["core_mandatory_remaining"] == [] and projected["total_units_done"] == 24
    assert projected["core_choice_remaining_count"] == 2  # FT5010 done, two more FT50xx to go
    [main] = [g for g in result["groups"] if g["slot_id"] == "plan"]
    assert main["label"] == "Plan for AY2026/27 Sem2"
    clash_notes = [r["caution"] for r in main["recommendations"] if r["course_code"] == "CS5242"]
    assert clash_notes == ["Clashes with BMD5302 (Monday 18:30–21:30)"]
