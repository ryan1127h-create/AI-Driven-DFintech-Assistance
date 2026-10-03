"""course_recommendation_tool builds its report from the profile's "course"
facts: role resolution (message > main_target_role > first family),
background texts, completed + current courses — and notes the other listed
roles. Knowledge and profile lookups are stubbed; no database, no LLM."""

from __future__ import annotations

import pytest

from app.tools.specialist import course_recommendation_tool as tool

_LABELS = {
    "degree_discipline_category": {"cs_se": "Computer science / software engineering"},
    "prior_coursework": {"programming": "Programming", "databases": "Databases"},
    "code_level": {"3": "Has built a complete project with tests"},
    "tech_stack": {"python": "Python", "sql": "SQL"},
    "target_role_families": {"data_analytics": "Data Analytics", "blockchain": "Blockchain",
                             "machine_learning_ai": "Machine Learning & AI"},
}


def _describe(key, value):
    labels = _LABELS.get(key, {})
    values = value if isinstance(value, list) else [value]
    return ", ".join(labels.get(str(v), str(v)) for v in values)


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(tool, "describe_value", _describe)
    monkeypatch.setattr(tool, "match_role_tag", lambda text: "blockchain" if "blockchain" in text.lower() else None)
    monkeypatch.setattr(tool, "get_role_profile", lambda tag: {
        "role_id": tag, "role_title": _LABELS["target_role_families"][tag], "required_skills": ["programming"]})
    monkeypatch.setattr(tool, "list_course_tags", lambda: {"FT5005": ["data_analytics"], "FT5004": ["blockchain"]})
    monkeypatch.setattr(tool, "list_role_tags", lambda: [])
    monkeypatch.setattr(tool, "list_course_electives", lambda: {})
    monkeypatch.setattr(tool, "list_courses", lambda: [])
    monkeypatch.setattr(tool, "list_curriculum_rules", lambda: [])
    monkeypatch.setattr(tool, "derived_course_notes", lambda uid: {"readiness": [], "graduation": []})


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


def test_role_named_in_the_message_wins():
    assert tool._resolve_role_tag(FACTS, "I want a blockchain job") == "blockchain"


def test_main_role_then_first_family():
    assert tool._resolve_role_tag({**FACTS, "main_target_role": "machine_learning_ai"}, None) == "machine_learning_ai"
    assert tool._resolve_role_tag({**FACTS, "main_target_role": "machine_learning_ai"}, "quant trader") == "machine_learning_ai"
    assert tool._resolve_role_tag(FACTS, None) == "data_analytics"
    assert tool._resolve_role_tag({}, None) is None


def test_request_is_built_from_profile_facts():
    request = tool.build_request(FACTS, "data_analytics")
    assert request["goals"] == {"target_role": "Data Analytics", "target_industry": None}
    assert request["role_profile"]["role_id"] == "data_analytics"
    assert request["curated_role_courses"] == ["FT5005"]
    background = request["background"]
    assert background["academic_background"] == (
        "Computer science / software engineering; prior coursework: Programming, Databases")
    assert background["tech_level"] == (
        "Programming: Has built a complete project with tests; Machine learning: 2; tech stack: Python, SQL")
    assert background["completed_courses"] == ["BMD5301", "FT5005"]  # completed + current, deduplicated


def test_no_profile_means_an_unpersonalised_request():
    request = tool.build_request({}, None)
    assert request["goals"]["target_role"] is None and request["role_profile"] is None
    assert request["background"]["academic_background"] is None
    assert request["background"]["completed_courses"] == []


def test_other_listed_roles_are_noted(monkeypatch):
    from langchain_core.messages import HumanMessage

    from app.tools.turn_context import TurnState

    captured = {}
    monkeypatch.setattr(tool, "get_profile_for_purpose", lambda uid, purpose: captured.setdefault("facts", FACTS))
    monkeypatch.setattr(tool, "recommend_courses", lambda request: {"notes": [], "request": request})
    monkeypatch.setattr(tool, "render_structured_reply",
                        lambda result, msg, prompt, on_event=None, depth=None: (result["notes"][-1], []))
    answer = tool._handler(TurnState(messages=[HumanMessage("courses?")], user_id="u1"))
    assert answer.text == ("Planned around the main target role; the profile also lists: "
                           "Blockchain, Machine Learning & AI.")


def test_derived_notes_extend_the_tech_level_and_the_reply_notes(monkeypatch):
    from langchain_core.messages import HumanMessage

    from app.tools.turn_context import TurnState

    monkeypatch.setattr(tool, "get_profile_for_purpose", lambda uid, purpose: FACTS)
    monkeypatch.setattr(tool, "derived_course_notes", lambda uid: {
        "readiness": ["Readiness gap (derived): maths and statistics self-rated at level 1, below the level 2 the programme expects"],
        "graduation": ["Graduation risk (derived): GPA is below the 3.0 needed to graduate."],
    })
    captured = {}
    monkeypatch.setattr(tool, "recommend_courses", lambda request: captured.setdefault("result", {"notes": [], "request": request}))
    monkeypatch.setattr(tool, "render_structured_reply", lambda result, msg, prompt, on_event=None, depth=None: ("ok", []))
    tool._handler(TurnState(messages=[HumanMessage("courses?")], user_id="u1"))

    result = captured["result"]
    assert "maths and statistics self-rated at level 1" in result["request"]["background"]["tech_level"]
    assert "Graduation risk (derived): GPA is below the 3.0 needed to graduate." in result["notes"]

