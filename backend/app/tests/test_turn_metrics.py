"""Exercises the staff dashboard's usage statistics end to end, without a
database: orchestrator/turn_metrics.py reading every agent_used shape the
app produces, run_turn recording one metric per turn (and never failing a
turn over it), the audience lookup, and admin's overview turning the
stored rows into top topics and agent health."""

from __future__ import annotations

from types import SimpleNamespace

import psycopg
import pytest
from langchain_core.messages import AIMessage

from app.domains.admin import repository as admin_repository
from app.domains.admin import service as admin_service
from app.domains.conversation import service as conversation_service
from app.orchestrator import classification, turn_service
from app.orchestrator.turn_metrics import read_agent_used


@pytest.mark.parametrize("agent_used, agents, failed, outcome", [
    ("course_recommendation_agent", ["course_recommendation"], [], "answered"),
    ("financial_agent+revised", ["financial"], [], "revised"),
    ("course_recommendation_agent_fallback+revised", ["course_recommendation"], ["course_recommendation"], "fallback"),
    ("career_agent+comparison_agent", ["career", "comparison"], [], "answered"),
    ("admissions_agent+clarify", ["admissions"], [], "need_input"),
    ("admissions_timeout+faq_agent", ["admissions", "faq"], ["admissions"], "error"),
    ("admissions_unavailable+faq_unavailable", ["admissions", "faq"], ["admissions", "faq"], "error"),
    ("assessment_agent_unavailable", ["assessment"], ["assessment"], "error"),
    ("orchestrator_need_input", ["orchestrator"], [], "need_input"),
    ("orchestrator_decline", ["orchestrator"], [], "declined"),
    ("orchestrator_error", ["orchestrator"], ["orchestrator"], "error"),
    ("supervisor", ["supervisor"], [], "answered"),
    ("", [], [], "answered"),
])
def test_every_agent_used_shape_is_read(agent_used, agents, failed, outcome):
    result = read_agent_used(agent_used)
    assert (result.agents, result.failed_agents, result.outcome) == (agents, failed, outcome)


def _run_a_turn(monkeypatch, agent_used="financial_agent"):
    state = SimpleNamespace(history_summaries=[], raw_tail=[], declined_fields=[], turn_count=0, pending_turn_intents=[])
    conv = turn_service.conversation
    monkeypatch.setattr(conv, "new_session_id", lambda: "s1")
    monkeypatch.setattr(conv, "get_state", lambda sid, uid: state)
    monkeypatch.setattr(conv, "render_summaries", lambda summaries: "")
    monkeypatch.setattr(conv, "record_turn", lambda *a, **k: None)
    monkeypatch.setattr(turn_service, "get_profile_summary_text", lambda uid: "")
    monkeypatch.setattr(turn_service, "get_assistant_preferences", lambda uid: {"language_pref": [], "answer_depth": "standard"})
    monkeypatch.setattr(turn_service.classification, "classify_intent",
                        lambda messages, on_event=None, previous_turn=None: classification.Classification(["financial", "faq"]))
    monkeypatch.setattr(turn_service.dispatch, "answer_turn", lambda state, intents, on_event=None: (AIMessage("ok"), "ok", agent_used))
    return turn_service.run_turn(None, "How much are the fees?", "u1")


def test_a_turn_records_one_metric_without_its_text(monkeypatch, stored_turn_metrics):
    monkeypatch.setattr(conversation_service.settings, "session_store_backend", "supabase_cached")
    _run_a_turn(monkeypatch, "financial_agent+revised")
    [row] = stored_turn_metrics
    assert row["conversation_id"] == "s1" and row["user_id"] == "u1" and row["audience"] == "applicant"
    assert (row["intents"], row["agents"], row["failed_agents"], row["outcome"]) == (["financial", "faq"], ["financial"], [], "revised")
    assert isinstance(row["latency_ms"], int) and row["latency_ms"] >= 0
    assert "How much" not in repr(row)


def test_the_in_memory_store_records_nothing(monkeypatch, stored_turn_metrics):
    monkeypatch.setattr(conversation_service.settings, "session_store_backend", "memory")
    _run_a_turn(monkeypatch)
    assert stored_turn_metrics == []


def test_a_failing_metric_never_fails_the_turn(monkeypatch):
    monkeypatch.setattr(conversation_service.settings, "session_store_backend", "supabase_cached")

    def down(row):
        raise ConnectionError("db down")

    monkeypatch.setattr(conversation_service, "insert_turn_metric", down)
    assert _run_a_turn(monkeypatch).reply == "ok"

    def no_audience(user_id):
        raise RuntimeError("profile down")

    monkeypatch.setattr(turn_service, "get_audience", no_audience)
    assert _run_a_turn(monkeypatch).reply == "ok"


@pytest.mark.parametrize("role, stage, expected", [
    ("admin", "alumni", "admin"),
    ("user", "alumni", "alumni"),
    ("user", "current", "enrolled_student"),
    ("user", "applicant", "applicant"),
    ("user", None, "applicant"),
])
def test_audience(monkeypatch, role, stage, expected):
    from app.domains.auth import service as auth_service

    monkeypatch.setattr(auth_service.repository, "get_account", lambda uid: {"role": role})
    monkeypatch.setattr(auth_service, "_lifecycle_stage", lambda uid: stage)
    assert auth_service.get_audience("u1") == expected


def test_audience_is_unknown_when_the_account_cannot_be_read(monkeypatch):
    from app.domains.auth import service as auth_service

    def down(uid):
        raise ConnectionError("db down")

    monkeypatch.setattr(auth_service.repository, "get_account", down)
    assert auth_service.get_audience("u1") == "unknown"
    monkeypatch.setattr(auth_service.repository, "get_account", lambda uid: None)
    assert auth_service.get_audience("u1") == "unknown"


def test_the_overview_ranks_topics_per_audience_and_rates_agents():
    view = admin_service._usage_view({
        "available": True,
        "topics": [
            {"audience": "applicant", "intent": "admissions", "total": 5},
            {"audience": "enrolled_student", "intent": "course_recommendation", "total": 7},
            {"audience": "applicant", "intent": "course_recommendation", "total": 1},
            {"audience": "alumni", "intent": "career", "total": 2},
        ],
        "agents": [
            {"agent": "course_recommendation", "requests": 40, "failed": 1, "avg_latency_ms": 4200},
            {"agent": "admissions", "requests": 10, "failed": 1, "avg_latency_ms": 2000},
            {"agent": "comparison", "requests": 3, "failed": 0, "avg_latency_ms": 16000},
        ],
    })
    assert view["top_topics"]["all"] == [
        {"label": "Course Recommendation", "total": 8}, {"label": "Admissions", "total": 5}, {"label": "Career Planning", "total": 2},
    ]
    assert view["top_topics"]["applicant"][0] == {"label": "Admissions", "total": 5}
    assert view["top_topics"]["enrolled_student"] == [{"label": "Course Recommendation", "total": 7}]
    statuses = {a["name"]: (a["success"], a["status"]) for a in view["agents"]}
    # 1/40 failures is healthy; 1/10 is not; 16 s average is too slow.
    assert statuses == {"course_recommendation": (39, "Healthy"), "admissions": (9, "Degraded"), "comparison": (3, "Degraded")}


def test_usage_is_reported_unavailable_until_the_table_exists(monkeypatch):
    def missing(query, params=()):
        raise psycopg.errors.UndefinedTable('relation "chat.turn_metrics" does not exist')

    monkeypatch.setattr(admin_repository.reporting_db, "fetch_all_dict", missing)
    assert admin_repository.fetch_usage(7) == {"available": False, "topics": [], "agents": []}
    assert admin_service._usage_view(admin_repository.fetch_usage(7))["top_topics"]["all"] == []


def test_an_answer_pointing_to_the_official_pages_counts_as_a_fallback(monkeypatch):
    from app.domains.specialist.knowledge_qa import interface as knowledge_qa
    from app.domains.specialist.knowledge_qa import service as qa_service
    from app.tools.specialist import knowledge_qa_tool
    from app.tools.turn_context import TurnState
    from langchain_core.messages import HumanMessage

    monkeypatch.setattr(knowledge_qa_tool, "retrieve_context", lambda *a, **k: knowledge_qa_tool.RetrievedContext(text=None))
    monkeypatch.setattr(knowledge_qa_tool, "current_facts", lambda: knowledge_qa_tool.RetrievedContext(text=None))
    monkeypatch.setattr(knowledge_qa, "search_query", lambda message, history: message)
    state = TurnState(messages=[HumanMessage("What is the fee?")], user_id="u1")
    for text, used in ((qa_service.UNVERIFIED_REPLY_START + " ...", "financial_agent_fallback"),
                       ("The fee is listed on the programme page.", "financial_agent")):
        monkeypatch.setattr(knowledge_qa, "answer_topic", lambda *a, text=text, **k: text)
        assert knowledge_qa_tool.FINANCIAL_TOOL.handler(state).agent_used == used
