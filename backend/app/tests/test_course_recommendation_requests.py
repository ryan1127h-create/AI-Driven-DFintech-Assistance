"""What a request asks for, end to end and stage by stage: courses the
student excludes (hard, except mandatory ones), courses they ask for, a
stated Capstone intent, a declared Vertical, the request-matching signals
and their evidence, and the ad_hoc mode's single matching list."""

from __future__ import annotations

from app.domains.specialist.course_recommendation import interface
from app.domains.specialist.course_recommendation.models import CandidatePool, Course
from app.domains.specialist.course_recommendation.policy import curriculum as cs
from app.domains.specialist.course_recommendation.stages import s4_slots
from app.domains.specialist.course_recommendation.stages.s3_constraints import degree_progress, eligibility
from app.domains.specialist.course_recommendation.stages.s5_scoring import scorer, signals

V1, V2 = cs.TRACK_VERTICALS["computing_technologies"], cs.TRACK_VERTICALS["financial_data_analytics_intelligence"]


def _course(code: str, role: str = "elective", **overrides) -> Course:
    defaults = dict(
        code=code, title=code, units=4, section="", skills=(), description="", prerequisite_text="",
        preclusion_text="", can_recommend=True, source_url="", requirement_role=role, level=5000,
    )
    defaults.update(overrides)
    return Course(**defaults)


# ---- S3 ----------------------------------------------------------------------

def test_an_excluded_course_is_left_out_but_a_mandatory_one_stays():
    courses = [_course("FT5003", "core_choice"), _course("IT5006", "core_mandatory")]
    pool = eligibility.build_candidate_pool(courses, [], [], ["FT5003", "IT5006"])
    assert [c.code for c in pool.eligible] == ["IT5006"]
    assert pool.excluded_courses == ({"course_code": "FT5003", "reason": "excluded_by_student"},)
    assert pool.kept_mandatory == ("IT5006",)


def _core_done() -> tuple[list[Course], tuple[str, ...]]:
    courses = [_course(c, "core_mandatory") for c in cs.CORE_MANDATORY]
    courses += [_course(c, "core_choice") for c in sorted(cs.CORE_CHOICE_POOL)]
    done = tuple(cs.CORE_MANDATORY) + tuple(sorted(cs.CORE_CHOICE_POOL))[:3]
    return courses, done


def test_a_stated_choice_of_electives_sets_the_alternative_path():
    courses, done = _core_done()
    progress = degree_progress.compute(courses, done, 28, "electives_instead")
    assert progress.capstone_path == "elective_alternative_in_progress" and progress.capstone_from_intent
    assert progress.elective_units_target == 24


def test_a_stated_capstone_plan_keeps_the_base_target_until_ready():
    courses, done = _core_done()
    progress = degree_progress.compute(courses, done, 28, "capstone_research")
    assert progress.capstone_path == "direct_planned" and progress.elective_units_target == 12


def test_without_an_intent_the_path_is_inferred_as_before():
    courses, done = _core_done()
    progress = degree_progress.compute(courses, done, 28)
    assert progress.capstone_path == "undecided" and not progress.capstone_from_intent


# ---- S4 ----------------------------------------------------------------------

def test_a_declared_vertical_carries_the_elective_quota():
    tagged = [_course(c, vertical=(V1,), role_tags=(("data_analytics", "Data Analytics"),)) for c in ("A1", "A2")]
    declared = _course("B1", vertical=(V2,))
    courses = [*tagged, declared]
    pool = CandidatePool(eligible=tuple(courses), skill_gaps=(), completed_recognized=(),
                         completed_unrecognized=(), completed_units=0)
    progress = degree_progress.compute(courses, (), 0)
    slots = s4_slots.derive_slots(courses, pool, progress, "data_analytics", V2)
    primary = next(s for s in slots if s.slot_type == "elective" and s.required_pick_count > 0)
    assert "Vertical #2" in primary.label


# ---- S5 ----------------------------------------------------------------------

def _ctx(**overrides) -> signals.ScoringContext:
    defaults = dict(target_role_tag=None, role_skills=(), skill_gaps=frozenset(), skill_share={"ai_ml": 0.3},
                    preferences=(), project_averse=False)
    defaults.update(overrides)
    return signals.ScoringContext(**defaults)


def test_request_signals_score_what_the_student_asked_for():
    asked = _course("FT5011", skills=("ai_ml",), vertical=(V2,), workload_shape="lecture_heavy",
                    description="Deep learning for finance")
    scored = scorer.score_slot_candidates((asked,), _ctx(
        requested_codes=frozenset({"FT5011"}), preferred_skills=("ai_ml",), preferences=("deep learning",),
        interest_verticals=frozenset({V2}), prefers_lecture=True,
    ))[0]
    assert {item.signal: item.delta for item in scored.breakdown} == {
        "requested": 2.0, "preferred_skill": 1.5, "preference": 1.5, "vertical_interest": 1.0, "workload_fit": 1.0,
    }


# ---- end to end -------------------------------------------------------------

def _request(**overrides) -> dict:
    catalog = [
        {"code": "BMD5301", "title": "Intro to Finance", "units": 4, "can_recommend": True},
        {"code": "IT5006", "title": "Fundamentals of Data Analytics", "units": 4, "can_recommend": True},
        {"code": "FT5005", "title": "Machine Learning for Finance", "units": 4, "can_recommend": True,
         "description": "Machine learning methods applied to finance."},
        {"code": "FT5003", "title": "Blockchain Innovations", "units": 4, "can_recommend": True},
        {"code": "CS5246", "title": "Text Mining", "units": 4, "can_recommend": True, "vertical": [V2],
         "description": "Deep learning and text mining."},
        {"code": "CS5224", "title": "Cloud Computing", "units": 4, "can_recommend": True, "vertical": [V1]},
    ]
    return {"course_catalog": catalog, **overrides}


def test_ad_hoc_lists_matching_courses_with_the_requirement_each_counts_toward():
    result = interface.recommend_courses(_request(mode="ad_hoc", constraints={"keywords": ["deep learning"]}))
    assert result["mode"] == "ad_hoc"
    [group] = result["groups"]
    assert group["slot_type"] == "ad_hoc" and group["note"] is None
    [course] = group["recommendations"]
    assert course["course_code"] == "CS5246"
    assert course["counts_toward"].startswith("Vertical #2")
    assert "matches your interest in deep learning" in course["evidence"]


def test_ad_hoc_falls_back_to_best_fits_and_says_so_when_nothing_matches():
    result = interface.recommend_courses(_request(mode="ad_hoc", constraints={"keywords": ["quantum"]}))
    [group] = result["groups"]
    assert group["recommendations"] and group["note"].startswith("No course matched")


def test_a_semester_plan_without_its_semester_runs_as_the_overview():
    result = interface.recommend_courses(_request(mode="semester_plan"))
    assert result["mode"] == "degree_overview" and result["plan"] is None
    assert any("without knowing which semester" in note for note in result["notes"])


def test_exclusions_and_unavailable_requests_are_explained():
    result = interface.recommend_courses(_request(
        background={"completed_courses": ["FT5005"]},
        constraints={"exclude_codes": ["FT5003", "IT5006"], "include_codes": ["FT5005", "XX9999"]},
    ))
    codes = {r["course_code"] for g in result["groups"] for r in g["recommendations"]}
    assert "FT5003" not in codes and "IT5006" in codes
    notes = " ".join(result["notes"])
    assert "IT5006 is a mandatory core course" in notes
    assert "FT5005 can't be recommended: you've already completed it." in notes
    assert "XX9999 isn't in the programme's course catalogue." in notes


def test_ad_hoc_ranks_by_the_request_before_role_fit():
    # A course tagged for the target role but barely matching the request
    # must not lead one that matches the request better.
    catalog = _request()["course_catalog"] + [
        {"code": "IS4261", "title": "AI Business", "units": 4, "can_recommend": True, "vertical": [V1],
         "description": "Business innovation.", "role_tags": [{"tag": "data_analytics", "name": "Data Analytics"}],
         "skills": ["ai_ml"]},
        {"code": "CS5242", "title": "Neural Networks", "units": 4, "can_recommend": True, "vertical": [V2],
         "description": "Deep learning methods.", "skills": ["ai_ml"]},
    ]
    result = interface.recommend_courses({
        "course_catalog": catalog, "mode": "ad_hoc",
        "goals": {"target_role": "Data Analytics"},
        "role_profile": {"role_id": "data_analytics", "role_title": "Data Analytics", "required_skills": ["data_analytics"]},
        "constraints": {"keywords": ["deep learning"], "preferred_skills": ["ai_ml"]},
    })
    codes = [r["course_code"] for r in result["groups"][0]["recommendations"]]
    assert codes.index("CS5242") < codes.index("IS4261")
    assert not any("organised by Vertical" in note for note in result["notes"])


def test_sessions_and_structured_requirements_reach_the_domain():
    from app.domains.specialist.course_recommendation import workflow
    from app.domains.specialist.course_recommendation.contracts import CourseRecommendationInput

    request = CourseRecommendationInput.model_validate({"course_catalog": [{
        "code": "FT5007", "title": "Capstone", "units": 12, "can_recommend": True,
        "sessions": [{"ay": "2026-2027", "semester": 2, "lesson_type": "Lecture", "class_no": "1",
                      "day": "Monday", "start": "18:30", "end": "21:30"}],
        "prerequisites": {"all_of": [["IT5001X"]], "coreq_any_of": ["IT5006"], "unparsed": None},
    }]})
    [course] = workflow._courses_from_report(request)
    assert course.sessions[0].day == "Monday" and course.sessions[0].semester == 2
    assert course.prerequisite_groups == (("IT5001X",),) and course.corequisite_codes == ("IT5006",)


def test_a_time_window_must_be_two_ordered_clock_times():
    import pytest
    from pydantic import ValidationError

    from app.domains.specialist.course_recommendation.contracts import TimeWindowInput

    assert TimeWindowInput(start="18:00", end="23:00").start == "18:00"
    for start, end in (("21:00", "18:00"), ("6pm", "11pm"), ("25:00", "26:00")):
        with pytest.raises(ValidationError):
            TimeWindowInput(start=start, end=end)


def test_a_semester_plan_explains_why_a_requested_course_cant_be_taken():
    session = lambda s: [{"ay": "2026-2027", "semester": s, "lesson_type": "Lecture", "class_no": "1",
                          "day": "Monday", "start": "18:30", "end": "21:30"}]
    catalog = [
        {"code": "IT5006", "title": "Data Analytics", "units": 4, "can_recommend": True, "sessions": session(2)},
        {"code": "FT5011", "title": "Deep Learning", "units": 4, "can_recommend": True, "sessions": session(1)},
        {"code": "FT5010", "title": "Algo Trading", "units": 4, "can_recommend": True, "sessions": session(2),
         "prerequisites": {"all_of": [["IT5001", "IT5001X"]]}},
    ]
    result = interface.recommend_courses({
        "course_catalog": catalog, "mode": "semester_plan",
        "planning": {"ay": "2026-2027", "semester": 2, "label": "AY2026/27 Sem2"},
        "constraints": {"include_codes": ["FT5011", "FT5010"]},
    })
    notes = " ".join(result["notes"])
    assert "FT5011 can't be recommended: it doesn't run in the semester being planned." in notes
    assert "FT5010 can't be recommended: its prerequisite isn't completed yet." in notes
