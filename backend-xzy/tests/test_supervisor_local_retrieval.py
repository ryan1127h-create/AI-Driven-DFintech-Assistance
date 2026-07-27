"""When a user_query is supplied without external rag_chunks, the supervisor
retrieves locally and lets the gate decide (design doc 12 §3.6).

Absolute lexical scores are low/uncalibrated at this stage, so these tests assert
the integration's *direction* (off-topic escalates; on-topic surfaces the right
official source), not a specific answer/escalate tier — tier behaviour is locked
in after threshold calibration (a later task)."""
from __future__ import annotations

from common.mock_data import get_profile
import supervisor


def test_offtopic_query_escalates():
    profile = get_profile("1")
    resp = supervisor.route(
        "generate_application_checklist", profile,
        {"user_query": "What is the weather today in Tokyo?"},
    )
    assert resp.status == "escalated"
    assert resp.escalation is not None


def test_relevant_query_retrieves_matching_official_source():
    profile = get_profile("1")
    resp = supervisor.route(
        "generate_application_checklist", profile,
        {"user_query": "Do I need IELTS or TOEFL for English proficiency?",
         "namespace": "admissions"},
    )
    # Local retrieval ran and surfaced the correct official source, regardless of
    # whether the (uncalibrated) gate answered or escalated.
    sources = resp.data.get("sources", []) if resp.data else []
    assert "admissions_rules#english_proficiency" in sources
