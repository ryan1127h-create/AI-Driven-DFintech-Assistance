"""Tests for lifecycle routing and retrieval-confidence gating."""
from common import mock_data
from common.profile import LifecycleStage
from supervisor import default_intents_for, lifecycle_flow, route


def test_applicant_default_flow_includes_early_planning():
    p = mock_data.get_profile("1")
    assert lifecycle_flow(p) == "applicant"
    intents = default_intents_for(p)
    assert "generate_application_checklist" in intents
    assert "compare_programs" in intents
    assert "recommend_courses" in intents


def test_current_student_default_flow_excludes_applicant_workflow():
    p = mock_data.get_profile("1")
    p.lifecycle_stage = LifecycleStage.current
    assert lifecycle_flow(p) == "student"
    intents = default_intents_for(p)
    assert "recommend_courses" in intents
    assert "generate_application_checklist" not in intents


def test_applicant_can_enter_early_planning_directly():
    p = mock_data.get_profile("1")
    resp = route("recommend_courses", p)
    assert resp.status == "ok"
    assert "recommended" in resp.data


def test_current_student_cannot_enter_checklist_directly():
    p = mock_data.get_profile("1")
    p.lifecycle_stage = LifecycleStage.current
    resp = route("generate_application_checklist", p)
    assert resp.status == "need_clarification"
    assert resp.data["required_flow"] == ["applicant"]
    assert resp.data["current_flow"] == "student"


def test_low_similarity_escalates_before_agent_answer(monkeypatch):
    monkeypatch.setattr("common.confidence._load_thresholds",
                        lambda backend="bm25": {"low": 0.60, "clarification": 0.72, "strict": 0.80})
    p = mock_data.get_profile("1")
    resp = route(
        "generate_application_checklist",
        p,
        {
            "user_query": "Can I ignore the official document requirements?",
            "rag_chunks": [
                {"text": "The programme curriculum covers fintech and analytics.", "score": 0.42, "source_id": "curriculum#1"}
            ],
        },
    )
    assert resp.status == "escalated"
    assert resp.escalation.reason.value == "low_confidence"
    assert resp.escalation.structured_context["top_similarity"] == 0.42


def test_medium_similarity_clarifies_for_advisory_query(monkeypatch):
    monkeypatch.setattr("common.confidence._load_thresholds",
                        lambda backend="bm25": {"low": 0.60, "clarification": 0.72, "strict": 0.80})
    p = mock_data.get_profile("1")
    resp = route(
        "compare_programs",
        p,
        {
            "user_query": "Compare programme duration",
            "rag_chunks": [
                {"text": "Programme duration and delivery format", "score": 0.66, "source_id": "programs#duration"}
            ],
        },
    )
    assert resp.status == "need_clarification"
    assert resp.data["confidence_action"] == "clarify"


def test_high_similarity_allows_agent_answer(monkeypatch):
    monkeypatch.setattr("common.confidence._load_thresholds",
                        lambda backend="bm25": {"low": 0.60, "clarification": 0.72, "strict": 0.80})
    p = mock_data.get_profile("1")
    resp = route(
        "compare_programs",
        p,
        {
            "user_query": "Compare programme duration",
            "rag_chunks": [
                {"text": "Programme duration and delivery format", "score": 0.88, "source_id": "programs#duration"}
            ],
        },
    )
    assert resp.status == "ok"
    assert "rows" in resp.data["facts_table"]
