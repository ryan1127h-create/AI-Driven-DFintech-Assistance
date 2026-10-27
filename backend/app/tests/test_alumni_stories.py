"""tools/alumni_stories.py: which turns get alumni stories, from whose
consent, matched to what, and how they're added under the answer."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.tools import alumni_stories
from app.tools.contracts import ToolAnswer
from app.tools.turn_context import TurnState

STORY = {"name": "Daniel Tan", "position": "Quantitative Analyst", "company": "DBS Bank", "class_year": 2024,
         "bio": "Builds pricing models. " * 20, "matched": ["Quantitative Finance"]}


def _state(stage, **kw):
    return TurnState(messages=[HumanMessage("x")], user_id="u1", stage=stage, **kw)


def test_who_gets_stories():
    assert alumni_stories.audience("prospect", ["comparison"]) == "applicants"
    assert alumni_stories.audience("admitted", ["alumni"]) == "applicants"
    assert alumni_stories.audience("current", ["career"]) == "students"
    assert alumni_stories.audience("current", ["comparison"]) is None
    assert alumni_stories.audience("alumni", ["career"]) is None
    assert alumni_stories.audience("prospect", ["admissions"]) is None


def test_interests_put_the_field_asked_about_first(monkeypatch):
    monkeypatch.setattr(alumni_stories, "get_profile_for_purpose", lambda uid, purpose: {
        "main_target_role": "risk_management", "target_role_families": ["risk_management", "data_analytics"]})
    monkeypatch.setattr(alumni_stories, "match_role_tag", lambda text: None)
    state = _state("prospect", alumni_role_hint="quantitative_finance")
    assert alumni_stories.interests(state) == ["quantitative_finance", "risk_management", "data_analytics"]


def test_a_matching_story_is_added_for_the_right_audience(monkeypatch):
    calls = []

    def stories(audience, interests, limit=2):
        calls.append((audience, interests))
        return [STORY]
    monkeypatch.setattr(alumni_stories.alumni, "stories", stories)
    monkeypatch.setattr(alumni_stories, "get_profile_for_purpose", lambda uid, purpose: {"main_target_role": "quantitative_finance"})
    answer = alumni_stories.with_stories(ToolAnswer(text="Career advice."), _state("prospect"), ["career"])
    assert calls == [("applicants", ["quantitative_finance"])]
    assert answer.text.startswith("Career advice.\n\nAlumni with a similar path (shared by alumni for prospective students):")
    assert "**Daniel Tan** — Quantitative Analyst at DBS Bank, class of 2024." in answer.text
    assert answer.text.endswith("…") and "@" not in answer.text  # bio trimmed, no contact details


def test_no_story_without_a_match_a_fitting_turn_or_a_real_answer(monkeypatch):
    monkeypatch.setattr(alumni_stories.alumni, "stories", lambda audience, interests, limit=2: [])
    plain = ToolAnswer(text="Career advice.")
    assert alumni_stories.with_stories(plain, _state("prospect"), ["career"]) is plain
    monkeypatch.setattr(alumni_stories.alumni, "stories", lambda audience, interests, limit=2: [STORY])
    assert alumni_stories.with_stories(plain, _state("prospect"), ["financial"]) is plain
    question = ToolAnswer(text="Which role?", needs_clarification=True)
    assert alumni_stories.with_stories(question, _state("prospect"), ["career"]) is question


def test_a_failing_directory_never_breaks_the_answer(monkeypatch):
    def broken(audience, interests, limit=2):
        raise RuntimeError("db down")
    monkeypatch.setattr(alumni_stories.alumni, "stories", broken)
    plain = ToolAnswer(text="Career advice.")
    assert alumni_stories.with_stories(plain, _state("current"), ["career"]) is plain
