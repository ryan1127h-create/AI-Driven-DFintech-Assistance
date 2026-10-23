"""The chat's alumni tool: the student's matches from the Alumni Match
listing as a short reply and a card, narrowed to the field asked for when
anyone has it; the classifier's role hint; who the stage policy lets in."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from app.core import stage_policy
from app.orchestrator import classification
from app.tools.specialist import alumni_match_tool as tool
from app.tools.turn_context import TurnState

OPTIONS = [{"tag": "product_business", "label": "Product & Business"},
           {"tag": "risk_management", "label": "Risk Management"}]


def _person(n, expertise, request=None):
    return {"id": f"a{n}", "name": f"Alumnus {n}", "position": "Analyst", "company": "Bank", "class_year": 2023,
            "expertise": [{"tag": t, "label": t.replace("_", " ").title()} for t in expertise],
            "matched": [], "request": {"status": request} if request else None}


def _listing(items, can_send=True, ranked=True):
    return {"items": items, "total": len(items), "expertise_options": OPTIONS,
            "ranked_by_interests": ranked, "can_send_requests": can_send}


def _state(hint=None):
    return TurnState(messages=[HumanMessage("alumni?")], user_id="s1", stage="current", alumni_role_hint=hint)


def test_a_named_field_narrows_the_listing_and_shows_the_top_three(monkeypatch):
    calls = []

    def list_matches(uid, expertise=None):
        calls.append(expertise)
        return _listing([_person(i, ["product_business"]) for i in range(5)])
    monkeypatch.setattr(tool.alumni, "list_matches", list_matches)
    answer = tool._handler(_state("product_business"))
    assert calls == [["product_business"]]
    assert answer.text.startswith("Here are alumni working in Product & Business:")
    assert len(answer.card["items"]) == 3 and answer.card["kind"] == "alumni_matches"
    assert "Open one in Alumni Match" in answer.text


def test_no_one_in_the_field_falls_back_to_the_closest_matches(monkeypatch):
    def list_matches(uid, expertise=None):
        return _listing([] if expertise else [_person(1, ["risk_management"], request="pending")])
    monkeypatch.setattr(tool.alumni, "list_matches", list_matches)
    answer = tool._handler(_state("product_business"))
    assert "No listed alumni have Product & Business" in answer.text and "(Request sent)" in answer.text
    assert answer.card["items"][0]["request_status"] == "pending"


def test_without_the_consent_the_reply_says_how_to_turn_it_on(monkeypatch):
    monkeypatch.setattr(tool.alumni, "list_matches", lambda uid, expertise=None: _listing([_person(1, [])], can_send=False))
    answer = tool._handler(_state())
    assert "Settings → Privacy" in answer.text and answer.card["can_send_requests"] is False


def test_an_empty_directory_gets_no_card(monkeypatch):
    monkeypatch.setattr(tool.alumni, "list_matches", lambda uid, expertise=None: _listing([]))
    answer = tool._handler(_state())
    assert answer.card is None and "no alumni listed" in answer.text


def test_the_classifier_keeps_only_a_known_role_tag_for_alumni():
    parsed = classification._parse(json.dumps({"intents": ["alumni"], "alumni_role_hint": "product_business"}))
    assert parsed.intents == ["alumni"] and parsed.alumni_role_hint == "product_business"
    assert classification._parse(json.dumps({"intents": ["alumni"], "alumni_role_hint": "payments"})).alumni_role_hint is None
    assert classification._parse(json.dumps({"intents": ["career"], "alumni_role_hint": "risk_management"})).alumni_role_hint is None


def test_only_enrolled_students_get_the_matches():
    hints = {"course_recommendation": None, "career": None, "comparison": None}
    for stage in ("current", "graduating"):
        assert stage_policy.plan_turn(stage, ["alumni"], hints).intents == ["alumni"]
    for stage in ("prospect", "rejected", "applicant", "admitted"):
        plan = stage_policy.plan_turn(stage, ["alumni"], hints)
        assert plan.intents == [] and "opens once you've enrolled" in plan.replies[0]
    assert "requests waiting for you" in stage_policy.plan_turn("alumni", ["alumni"], hints).replies[0]
