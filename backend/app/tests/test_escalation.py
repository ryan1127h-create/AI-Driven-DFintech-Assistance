"""Exercises escalation end to end without a database: the classifier's
escalation signal, the open-or-offer rules, the case summary's fallback,
run_turn opening a case (or recording an offer) after the turn is saved,
taking an offer up, one open case per kind, the sensitive-message reroute,
and that a failed case never fails the turn. chat.cases is the in-memory
stand-in from conftest.stored_cases."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.errors import ForbiddenError, NotFoundError
from app.domains.conversation import service as conversation_service
from app.domains.specialist.escalation import policy, summary
from app.orchestrator import classification, turn_service


# --- the classifier's signal ---------------------------------------------------------

def _parsed(escalation):
    return classification._parse(json.dumps({"intents": ["general"], "escalation": escalation})).escalation


def test_the_classifier_signal_is_read_and_checked():
    assert _parsed(None) is None
    assert _parsed({"category": "complaint", "urgent": False}) == {"category": "complaint", "urgent": False}
    assert _parsed({"category": "sensitive", "urgent": False}) == {"category": "sensitive", "urgent": True}
    assert _parsed({"category": "low_confidence"}) is None  # only raised from the answer, never by the classifier
    assert _parsed({"category": "made_up"}) is None
    assert _parsed("explicit_request") is None
    assert classification._parse(json.dumps({"intents": ["admissions"]})).escalation is None


# --- the rules ---------------------------------------------------------------------

@pytest.mark.parametrize("signal, outcome, intents, expected", [
    ({"category": "explicit_request", "urgent": False}, "answered", ["general"], ("open", "explicit_request", "direct", "normal")),
    ({"category": "complaint", "urgent": True}, "answered", ["financial"], ("open", "complaint", "direct", "urgent")),
    ({"category": "sensitive", "urgent": False}, "answered", ["general"], ("open", "sensitive", "direct", "urgent")),
    ({"category": "policy_exception", "urgent": False}, "answered", ["financial"], ("offer", "policy_exception", "direct", "normal")),
    (None, "fallback", ["admissions"], ("offer", "low_confidence", "chained", "normal")),
    (None, "error", ["academic"], ("offer", "low_confidence", "chained", "normal")),
])
def test_what_is_opened_and_what_is_offered(signal, outcome, intents, expected):
    d = policy.decide(signal, outcome, intents)
    assert (d.action, d.category, d.trigger_source, d.priority) == expected


@pytest.mark.parametrize("outcome, intents", [("answered", ["admissions"]), ("revised", ["faq"]),
                                              ("need_input", ["career"]), ("error", ["off_topic"])])
def test_most_turns_need_no_human(outcome, intents):
    assert policy.decide(None, outcome, intents) is None


def test_origin_labels():
    assert policy.origin_label(["admissions", "faq"]) == "Admissions + FAQ"
    assert policy.origin_label(["orchestrator"]) == "Other"
    assert policy.origin_label([]) == "Other"


# --- the summary -------------------------------------------------------------------

def test_the_summary_is_about_the_message_that_raised_the_case(monkeypatch):
    seen = {}
    monkeypatch.setattr(summary.llm, "complete", lambda system, user, **k: seen.update(user=user) or "S")
    summary.summarize([("user", "talk to staff about my course plan"), ("assistant", "Sure, passing it on."),
                       ("user", "also: the enrolment email came two weeks late"), ("assistant", "Sorry about that.")],
                      "complaint")
    earlier, trigger = seen["user"].split("MESSAGE THAT RAISED THE CASE:")
    assert "two weeks late" in trigger and "course plan" not in trigger
    assert "course plan" in earlier and "Sorry about that" not in seen["user"]


def test_the_summary_falls_back_to_the_users_words(monkeypatch):
    transcript = [("user", "Hi"), ("assistant", "Hello!"), ("user", "  I want a fee waiver for next term.  ")]

    def down(*a, **k):
        raise ConnectionError("llm down")

    monkeypatch.setattr(summary.llm, "complete", down)
    assert summary.summarize(transcript, "policy_exception") == "I want a fee waiver for next term."
    monkeypatch.setattr(summary.llm, "complete", lambda *a, **k: "   ")
    assert summary.summarize(transcript, "policy_exception") == "I want a fee waiver for next term."
    monkeypatch.setattr(summary.llm, "complete", lambda *a, **k: "Applicant asks for a fee waiver.")
    assert summary.summarize(transcript, "policy_exception") == "Applicant asks for a fee waiver."


# --- in a turn ---------------------------------------------------------------------

@pytest.fixture()
def chat(monkeypatch):
    """run_turn with the LLM steps faked; returns a helper that runs one
    turn with a given classifier signal and agent_used."""
    monkeypatch.setattr(conversation_service.settings, "session_store_backend", "supabase_cached")
    state = SimpleNamespace(history_summaries=[], raw_tail=[], declined_fields=[], turn_count=0,
                            pending_turn_intents=[], user_id="u1")
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "new_session_id", lambda: "s1")
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state if uid == "u1" else pytest.fail("other user"))
    monkeypatch.setattr(conv, "render_summaries", lambda summaries: "")
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "")
    monkeypatch.setattr(turn_service, "get_assistant_preferences", lambda uid: {"language_pref": [], "answer_depth": "standard"})
    monkeypatch.setattr(turn_service.escalation, "summarize", lambda transcript, category: f"summary of {len(transcript)} messages")
    saved = []

    def record_turn(sid, st, human, ai, intents, agent_used, escalation_offer=None):
        st.turn_count += 1
        st.raw_tail = st.raw_tail + [human, ai]
        st.pending_turn_intents = st.pending_turn_intents + [
            {"turn": st.turn_count, "intents": intents, "agent_used": agent_used,
             **({"escalation_offer": escalation_offer} if escalation_offer else {})}]
        saved.append(sid)

    monkeypatch.setattr(conv, "record_turn", record_turn)
    seen = {}

    def run(signal=None, agent_used="supervisor", intents=("general",), message="hello"):
        monkeypatch.setattr(turn_service.classification, "classify_intent",
                            lambda messages, on_event=None, previous_turn=None:
                            classification.Classification(list(intents), escalation=signal))

        def answer_turn(turn_state, routed_intents, on_event=None):
            seen["intents"] = routed_intents
            return AIMessage("ok"), "ok", agent_used

        monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)
        return turn_service.run_turn(None if not saved else "s1", message, "u1")

    return SimpleNamespace(run=run, state=state, saved=saved, seen=seen)


def test_asking_for_a_person_opens_a_case_after_the_turn_is_saved(chat, stored_cases):
    result = chat.run({"category": "explicit_request", "urgent": False}, "admissions_agent", ["admissions"])
    assert chat.saved == ["s1"]
    [case] = stored_cases
    assert {k: case[k] for k in ("user_id", "conversation_id", "category", "trigger_source", "priority", "origin_specialist")} == {
        "user_id": "u1", "conversation_id": "s1", "category": "explicit_request", "trigger_source": "direct",
        "priority": "normal", "origin_specialist": "Admissions",
    }
    assert case["summary"] == "summary of 2 messages"
    assert result.escalation["kind"] == "opened" and result.escalation["case"]["created"] is True
    assert "resources" not in result.escalation


def test_the_case_card_survives_the_streams_json_encoding(chat, stored_cases):
    # The /chat/stream "done" event is encoded with json.dumps (a datetime
    # in the card broke it in the browser check).
    result = chat.run({"category": "complaint", "urgent": False})
    assert json.loads(json.dumps(result.escalation))["case"]["category"] == "complaint"


def test_the_answer_is_told_about_the_hand_off(chat, monkeypatch):
    seen = {}
    monkeypatch.setattr(turn_service.classification, "classify_intent",
                        lambda messages, on_event=None, previous_turn=None:
                        classification.Classification(["general"], escalation={"category": "explicit_request", "urgent": False}))

    def answer_turn(turn_state, intents, on_event=None):
        seen["messages"] = turn_state.messages
        return AIMessage("ok"), "ok", "supervisor"

    monkeypatch.setattr(turn_service.dispatch, "answer_turn", answer_turn)
    turn_service.run_turn(None, "can I talk to a person?", "u1")
    assert seen["messages"][-2].content == turn_service.escalation.HANDOFF_NOTE
    assert seen["messages"][-1].content == "can I talk to a person?"


def test_an_offer_does_not_tell_the_answer_anything(chat):
    chat.run({"category": "policy_exception", "urgent": False}, "financial_agent", ["financial"])
    assert all(m.content != turn_service.escalation.HANDOFF_NOTE for m in chat.state.raw_tail)


def test_a_second_request_reuses_the_open_case(chat, stored_cases):
    chat.run({"category": "complaint", "urgent": False})
    again = chat.run({"category": "complaint", "urgent": False})
    assert len(stored_cases) == 1 and again.escalation["case"]["created"] is False


def test_a_sensitive_message_is_never_declined_and_comes_with_support(chat, stored_cases):
    result = chat.run({"category": "sensitive", "urgent": True}, intents=("off_topic",))
    assert chat.seen["intents"] == ["general"]
    assert stored_cases[0]["priority"] == "urgent"
    assert result.escalation["resources"]


def test_an_offer_is_recorded_and_only_opened_when_taken_up(chat, stored_cases):
    result = chat.run(None, "course_recommendation_agent_fallback", ["course_recommendation"])
    assert result.escalation == {"kind": "offer", "category": "low_confidence"}
    assert stored_cases == []
    assert chat.state.pending_turn_intents[-1]["escalation_offer"]["trigger_source"] == "chained"
    card = turn_service.accept_escalation_offer("s1", "u1")
    assert card["kind"] == "opened" and stored_cases[0]["category"] == "low_confidence"
    assert stored_cases[0]["origin_specialist"] == "Course Recommendation"


def test_only_the_latest_turns_offer_can_be_taken_up(chat, stored_cases):
    chat.run({"category": "policy_exception", "urgent": False}, "financial_agent", ["financial"])
    chat.run(None, "financial_agent", ["financial"])  # the next turn made no offer
    with pytest.raises(NotFoundError):
        turn_service.accept_escalation_offer("s1", "u1")
    assert stored_cases == []


def test_someone_elses_conversation_cannot_be_escalated(chat, monkeypatch):
    chat.run({"category": "policy_exception", "urgent": False})

    def not_yours(sid, uid):
        raise ForbiddenError("This conversation belongs to a different user.")

    monkeypatch.setattr(turn_service.conversation, "get_state", not_yours)
    with pytest.raises(ForbiddenError):
        turn_service.accept_escalation_offer("s1", "intruder")


def test_a_case_that_cannot_be_stored_never_fails_the_turn(chat, monkeypatch):
    def down(case):
        raise ConnectionError("db down")

    monkeypatch.setattr(conversation_service, "insert_case", down)
    result = chat.run({"category": "explicit_request", "urgent": False})
    assert result.reply == "ok" and result.escalation is None


def test_ordinary_turns_carry_no_escalation(chat, stored_cases):
    assert chat.run(None, "admissions_agent", ["admissions"]).escalation is None
    assert "escalation_offer" not in chat.state.pending_turn_intents[-1]
    assert stored_cases == []


def test_users_see_their_own_cases_without_staff_notes(chat, stored_cases):
    chat.run({"category": "complaint", "urgent": False})
    [item] = conversation_service.list_cases("u1")
    assert set(item) == {"id", "short_id", "conversation_id", "category", "status", "priority", "created_at", "resolved_at"}
    assert conversation_service.list_cases("someone-else") == []


def test_the_transcript_for_a_summary_is_the_recent_messages():
    state = SimpleNamespace(raw_tail=[HumanMessage("a"), AIMessage("b"), HumanMessage("c"), AIMessage("d")])
    assert conversation_service.recent_transcript(state, 3) == [("assistant", "b"), ("user", "c"), ("assistant", "d")]
