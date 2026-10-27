"""The course_recommendation tool builds its report from the profile's
"course" facts: role resolution (message > main_target_role > first
family), background texts, completed + current courses — and notes the
other listed roles. prefetch.py gathers (knowledge and profile lookups are
stubbed here — no database, no LLM), builder.py assembles."""

from __future__ import annotations

import pytest

from app.tools.specialist.course_recommendation import tool
from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.specialist.course_recommendation.s2_assembly import builder, prefetch
from app.tools.specialist.course_recommendation.s7_presentation import renderer

_LABELS = {
    "degree_discipline_category": {"cs_se": "Computer science / software engineering"},
    "prior_coursework": {"programming": "Programming", "databases": "Databases"},
    "code_level": {"3": "Has built a complete project with tests"},
    "tech_stack": {"python": "Python", "sql": "SQL"},
    "target_role_families": {"data_analytics": "Data Analytics", "blockchain": "Blockchain",
                             "machine_learning_ai": "Machine Learning & AI"},
}

FACTS = {
    "target_role_families": ["data_analytics", "blockchain", "machine_learning_ai"],
    "degree_discipline_category": "cs_se",
    "prior_coursework": ["programming", "databases"],
    "code_level": 3,
    "ml_ai_level": 2,
    "tech_stack": ["python", "sql"],
    "completed_modules": [{"course_code": "BMD5301", "term": "AY2026/27 Sem1"}],
    "current_modules": [{"course_code": "FT5005"}, {"course_code": "BMD5301"}],
}

NO_DERIVED = {"readiness": [], "graduation": []}


def _describe(key, value):
    labels = _LABELS.get(key, {})
    values = value if isinstance(value, list) else [value]
    return ", ".join(labels.get(str(v), str(v)) for v in values)


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(prefetch, "describe_value", _describe)
    monkeypatch.setattr(prefetch, "match_role_tag", lambda text: "blockchain" if "blockchain" in text.lower() else None)
    monkeypatch.setattr(prefetch, "get_role_profile", lambda tag: {
        "role_id": tag, "role_title": _LABELS["target_role_families"][tag], "required_skills": ["programming"]})
    monkeypatch.setattr(prefetch, "list_course_tags", lambda: {"FT5005": ["data_analytics"], "FT5004": ["blockchain"]})
    monkeypatch.setattr(prefetch, "list_role_tags", lambda: [])
    monkeypatch.setattr(prefetch, "list_course_electives", lambda: {})
    monkeypatch.setattr(prefetch, "list_courses", lambda: [])
    monkeypatch.setattr(prefetch, "list_curriculum_rules", lambda: [])
    monkeypatch.setattr(prefetch, "list_course_schedule", lambda: {})
    monkeypatch.setattr(prefetch, "get_profile_for_purpose", lambda uid, purpose: FACTS)
    monkeypatch.setattr(prefetch, "derived_course_notes", lambda uid: NO_DERIVED)
    monkeypatch.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: None)
    monkeypatch.setattr(tool.parser, "parse", lambda message, mode: ParsedRequest())


def test_role_named_in_the_message_wins():
    assert prefetch.resolve_role_tag(FACTS, "I want a blockchain job") == "blockchain"


def test_main_role_then_first_family():
    assert prefetch.resolve_role_tag({**FACTS, "main_target_role": "machine_learning_ai"}, None) == "machine_learning_ai"
    assert prefetch.resolve_role_tag({**FACTS, "main_target_role": "machine_learning_ai"}, "quant trader") == "machine_learning_ai"
    assert prefetch.resolve_role_tag(FACTS, None) == "data_analytics"
    assert prefetch.resolve_role_tag({}, None) is None


def test_request_is_built_from_profile_facts():
    request = builder.build_request(prefetch.prefetch("u1", None))
    assert request["goals"] == {"target_role": "Data Analytics"}
    assert request["role_profile"]["role_id"] == "data_analytics"
    background = request["background"]
    assert background["academic_background"] == (
        "Computer science / software engineering; prior coursework: Programming, Databases")
    assert background["tech_level"] == (
        "Programming: Has built a complete project with tests; Machine learning: 2; tech stack: Python, SQL")
    assert background["completed_courses"] == ["BMD5301", "FT5005"]  # completed + current, deduplicated


def test_planned_courses_count_as_taken_except_in_a_semester_plan(monkeypatch):
    facts = {**FACTS, "planned_modules": [{"course_code": "CS5446", "term": "AY2026/27 Sem2"}]}
    monkeypatch.setattr(prefetch, "get_profile_for_purpose", lambda uid, purpose: facts)
    fetched = prefetch.prefetch("u1", None)
    overview = builder.build_request(fetched, ParsedRequest(mode="degree_overview"))
    plan = builder.build_request(fetched, ParsedRequest(mode="semester_plan"))
    assert overview["background"]["completed_courses"] == ["BMD5301", "FT5005", "CS5446"]
    assert plan["background"]["completed_courses"] == ["BMD5301", "FT5005"]
    assert builder.progress_basis(facts) == {
        "completed": ["BMD5301"], "in_progress": ["FT5005", "BMD5301"], "planned": ["CS5446"]}


def test_no_user_means_an_unpersonalised_request():
    request = builder.build_request(prefetch.prefetch(None, None))
    assert request["goals"]["target_role"] is None and request["role_profile"] is None
    assert request["background"]["academic_background"] is None
    assert request["background"]["completed_courses"] == []


def test_other_listed_roles_are_noted(monkeypatch):
    from langchain_core.messages import HumanMessage

    from app.tools.turn_context import TurnState

    monkeypatch.setattr(tool, "recommend_courses", lambda request: {"notes": [], "request": request})
    monkeypatch.setattr(renderer, "render_structured_reply",
                        lambda view, msg, prompt, on_event=None, depth=None, language=None, other_tools=(): (view["notes"][-1], []))
    answer = tool._handler(TurnState(messages=[HumanMessage("courses?")], user_id="u1"))
    assert answer.text == ("Planned around the main target role; the profile also lists: "
                           "Blockchain, Machine Learning & AI.")


def test_derived_notes_extend_the_tech_level_and_the_reply_notes(monkeypatch):
    from langchain_core.messages import HumanMessage

    from app.tools.turn_context import TurnState

    monkeypatch.setattr(prefetch, "derived_course_notes", lambda uid: {
        "readiness": ["Readiness gap (derived): maths and statistics self-rated at level 1, below the level 2 the programme expects"],
        "graduation": ["Graduation risk (derived): GPA is below the 3.0 needed to graduate."],
    })
    captured = {}
    monkeypatch.setattr(tool, "recommend_courses", lambda request: captured.setdefault("result", {"notes": [], "request": request}))
    monkeypatch.setattr(renderer, "render_structured_reply", lambda view, msg, prompt, on_event=None, depth=None, language=None, other_tools=(): ("ok", []))
    tool._handler(TurnState(messages=[HumanMessage("courses?")], user_id="u1"))

    result = captured["result"]
    assert "maths and statistics self-rated at level 1" in result["request"]["background"]["tech_level"]
    assert "Graduation risk (derived): GPA is below the 3.0 needed to graduate." in result["notes"]


def test_unreadable_profile_runs_unpersonalised_and_says_so(monkeypatch):
    def _fail(*args):
        raise RuntimeError("profile db down")

    monkeypatch.setattr(prefetch, "get_profile_for_purpose", _fail)
    monkeypatch.setattr(prefetch, "derived_course_notes", _fail)
    fetched = prefetch.prefetch("u1", None)
    assert fetched.facts == {} and fetched.role_tag is None
    assert fetched.readiness_notes == () and fetched.graduation_notes == ()
    assert fetched.notes == ("Your profile couldn't be read just now, so this recommendation isn't personalised.",)


def test_unreadable_catalogue_fails_the_turn(monkeypatch):
    def _fail():
        raise RuntimeError("knowledge db down")

    monkeypatch.setattr(prefetch, "list_courses", _fail)
    with pytest.raises(RuntimeError, match="knowledge db down"):
        prefetch.prefetch("u1", None)


def test_the_request_carries_what_the_message_asked_for(monkeypatch):
    facts = {**FACTS, "track_interest": ["computing_technologies"], "track_chosen": "financial_data_analytics_intelligence",
             "capstone_intent": "capstone_research"}
    monkeypatch.setattr(prefetch, "get_profile_for_purpose", lambda uid, purpose: facts)
    parsed = ParsedRequest(
        mode="ad_hoc", include_codes=["FT5011"], exclude_codes=["FT5003"], keywords=["deep learning"],
        workload_style="lecture", capstone_intent="electives_instead",
    )
    request = builder.build_request(prefetch.prefetch("u1", None), parsed)
    assert request["mode"] == "ad_hoc"
    assert request["student"] == {
        "study_mode": None,
        "capstone_intent": "electives_instead",  # stated in the message, wins over the profile
        "track_interest": ["computing_technologies"],
        "track_chosen": "financial_data_analytics_intelligence",
    }
    assert request["constraints"]["include_codes"] == ["FT5011"]
    assert request["constraints"]["exclude_codes"] == ["FT5003"]
    assert request["constraints"]["workload_style"] == "lecture"


def test_consent_off_is_said_in_the_reply_notes(monkeypatch):
    monkeypatch.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    monkeypatch.setattr(prefetch, "get_profile_for_purpose", lambda uid, purpose: {})
    assert any("Personalised recommendations are turned off" in note for note in prefetch.prefetch("u1", None).notes)


def test_a_semester_plan_request_carries_its_planning():
    from datetime import date

    parsed = ParsedRequest(mode="semester_plan", target_semester="next", unit_cap=12,
                           avoid_time_windows=[{"start": "18:00", "end": "23:00"}], study_mode="part_time")
    request = builder.build_request(prefetch.prefetch("u1", None), parsed, today=date(2026, 10, 10))
    assert request["planning"] == {"ay": "2026-2027", "semester": 2, "label": "AY2026/27 Sem2", "requested_units": 12}
    assert request["student"]["study_mode"] == "part_time"
    assert request["constraints"]["avoid_time_windows"] == [{"start": "18:00", "end": "23:00"}]


def test_other_modes_carry_no_planning():
    assert builder.build_request(prefetch.prefetch("u1", None), ParsedRequest(mode="ad_hoc"))["planning"] is None
