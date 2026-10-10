"""Exercises the domain's timetable.py and S5's time-preference signal: a
time or day the student wants kept free only counts against a course when
they couldn't avoid it — every class of some lesson type meets then — and
most of the programme meeting in the evening gets said, not hidden."""

from __future__ import annotations

from app.domains.specialist.course_recommendation import interface, timetable
from app.domains.specialist.course_recommendation.models import Course, Session
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer, signals

S1, S2 = ("2026-2027", 1), ("2026-2027", 2)
EVENING = (("18:00", "23:00"),)


def _slot(term, lesson, class_no, day, start, end) -> Session:
    return Session(term[0], term[1], lesson, class_no, day, start, end)


def _course(code: str, *sessions: Session) -> Course:
    return Course(code=code, title=code, units=4, section="", skills=(), description="",
                  prerequisite_text="", preclusion_text="", can_recommend=True, source_url="",
                  sessions=sessions)


EVENING_LECTURE = _course("FT5011", _slot(S1, "Lecture", "1", "Wednesday", "18:30", "21:30"))
# Tutorials in the evening or the morning: the morning class avoids it.
CHOICE = _course(
    "CS5242",
    _slot(S2, "Lecture", "1", "Monday", "09:00", "11:00"),
    _slot(S2, "Tutorial", "1", "Monday", "20:30", "21:30"),
    _slot(S2, "Tutorial", "2", "Tuesday", "10:00", "11:00"),
)


def test_a_fixed_evening_class_is_forced():
    slot = timetable.forced_avoided_slot(EVENING_LECTURE, S1, EVENING, frozenset())
    assert (slot.day, slot.start) == ("Wednesday", "18:30")


def test_a_lesson_type_with_a_clear_class_isnt_forced():
    assert timetable.forced_avoided_slot(CHOICE, S2, EVENING, frozenset()) is None


def test_a_day_to_keep_free_counts_too():
    assert timetable.forced_avoided_slot(CHOICE, S2, (), frozenset({"Monday"})) is not None


def test_overlaps_needs_the_same_day_and_crossing_times():
    a = _slot(S2, "Lecture", "1", "Monday", "18:30", "20:30")
    assert timetable.overlaps(a, _slot(S2, "Lecture", "1", "Monday", "20:00", "21:00"))
    assert not timetable.overlaps(a, _slot(S2, "Lecture", "1", "Monday", "20:30", "21:30"))  # back to back
    assert not timetable.overlaps(a, _slot(S2, "Lecture", "1", "Tuesday", "18:30", "20:30"))


def _ctx(**kw) -> signals.ScoringContext:
    return signals.ScoringContext(target_role_tag=None, role_skills=(), skill_gaps=frozenset(), skill_share={},
                                  preferences=(), project_averse=False, **kw)


def test_the_signal_scores_a_forced_slot_down_and_says_when():
    scored = scorer.score_slot_candidates((EVENING_LECTURE, CHOICE), _ctx(avoid_windows=EVENING))
    by_code = {s.course.code: s for s in scored}
    [item] = by_code["FT5011"].breakdown
    assert (item.signal, item.delta) == ("avoid_time", -1.0)
    assert item.evidence == "meets at a time you want kept free (Wednesday 18:30–21:30)"
    assert by_code["CS5242"].breakdown == ()


def test_outside_a_plan_a_clear_semester_is_enough():
    # Evening in Semester 1, daytime in Semester 2: it can be taken then.
    both = _course("IT5006",
                   _slot(S1, "Lecture", "1", "Thursday", "18:30", "20:30"),
                   _slot(S2, "Lecture", "1", "Thursday", "09:00", "11:00"))
    assert signals.forced_avoided_slot(both, _ctx(avoid_windows=EVENING)) is None
    assert signals.forced_avoided_slot(both, _ctx(avoid_windows=EVENING, plan_term=S1)) is not None


def test_no_preference_no_signal():
    assert scorer.score_slot_candidates((EVENING_LECTURE,), _ctx())[0].breakdown == ()


def test_most_courses_in_avoided_times_is_said():
    evening = lambda: [{"ay": "2026-2027", "semester": 1, "lesson_type": "Lecture", "class_no": "1",
                        "day": "Monday", "start": "18:30", "end": "21:30"}]
    catalog = [{"code": c, "title": c, "units": 4, "can_recommend": True, "sessions": evening()}
               for c in ("IT5006", "BMD5302", "FT5009")]
    result = interface.recommend_courses({
        "course_catalog": catalog, "constraints": {"avoid_time_windows": [{"start": "18:00", "end": "23:00"}]},
    })
    assert any("3 of the 3 courses open to you meet at times you want kept free" in n for n in result["notes"])
    evidence = [e for g in result["groups"] for r in g["recommendations"] for e in r["evidence"]]
    assert "meets at a time you want kept free (Monday 18:30–21:30)" in evidence
