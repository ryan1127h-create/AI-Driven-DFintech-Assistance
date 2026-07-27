"""Deterministic tests for #4 checklist rule engine (no LLM dependency)."""
from datetime import date

from agents.checklist.agent import handle
from agents.checklist.engine import build_checklist, urgency_for
from common import mock_data
from common.profile import DegreeClassification


def _keys(result):
    return {it.key for it in result.items}


def _item(result, key):
    return next(it for it in result.items if it.key == key)


def test_overseas_applicant_gets_official_docs_and_english_condition():
    # Profile 1: overseas CS grad, 2y work, full-time, country IN.
    p = mock_data.get_profile("1")
    r = build_checklist(p)
    keys = _keys(r)
    assert {"personal_statement", "cv", "proof_of_residence", "degree_certificate", "transcript", "referee_reports"} <= keys
    assert "english_proficiency" in keys  # IN not exempt


def test_local_part_time_applicant():
    # Profile 3: local NUS engineering grad, part-time, SG.
    p = mock_data.get_profile("3")
    r = build_checklist(p)
    keys = _keys(r)
    assert "english_proficiency" not in keys  # SG exempt
    assert "proof_of_residence" in keys
    assert "referee_reports" in keys


def test_missing_count_reflects_submitted_docs():
    p = mock_data.get_profile("3")  # submitted only ["cv"]
    r = build_checklist(p)
    submitted = [it for it in r.items if it.status == "submitted"]
    assert {it.key for it in submitted} == {"cv"}
    assert r.missing_count == len(r.items) - 1


def test_determinism():
    p = mock_data.get_profile("1")
    a = build_checklist(p)
    b = build_checklist(p)
    assert [(i.key, i.status) for i in a.items] == [(i.key, i.status) for i in b.items]


def test_handle_needs_clarification_without_background():
    p = mock_data.get_profile("1")
    p.academic_background = None
    resp = handle(p)
    assert resp.status == "need_clarification"
    assert "academic_background" in resp.missing_fields


def test_handle_envelope_shape():
    p = mock_data.get_profile("1")
    resp = handle(p)  # LLM offline -> deterministic fallback
    assert resp.status == "ok"
    assert resp.answer_type == "official"
    assert "items" in resp.data and resp.data["items"]
    assert all({"key", "label", "status", "why"} <= set(it) for it in resp.data["items"])


# ---------- v2: extended rules ----------
def test_new_base_items_always_present():
    r = build_checklist(mock_data.get_profile("1"))
    assert {"referee_reports", "application_fee", "financial_support"} <= _keys(r)


def test_other_supporting_documents_is_optional():
    p = mock_data.get_profile("4")
    item = _item(build_checklist(p), "other_supporting_documents")
    assert item.required is False


def test_high_classification_no_extra_academic_statement():
    p = mock_data.get_profile("4")
    p.academic_background.degree_classification = DegreeClassification.first
    assert "academic_justification" not in _keys(build_checklist(p))


def test_unknown_classification_no_extra_academic_statement():
    p = mock_data.get_profile("4")
    p.academic_background.degree_classification = DegreeClassification.unknown
    assert "academic_justification" not in _keys(build_checklist(p))


# ---------- v2: rich document status ----------
def test_document_status_takes_precedence():
    p = mock_data.get_profile("4")
    r = build_checklist(p, today=date(2026, 5, 31))
    assert _item(r, "cv").status == "verified"
    assert _item(r, "transcript").status == "rejected"
    assert _item(r, "personal_statement").status == "under_review"


def test_outstanding_counts_missing_and_rejected_only():
    p = mock_data.get_profile("4")
    r = build_checklist(p, today=date(2026, 5, 31))
    # verified + under_review are NOT outstanding; rejected IS.
    assert r.outstanding_count == sum(
        1 for it in r.items if it.required and it.status in ("missing", "rejected")
    )
    assert _item(r, "cv").status not in ("missing", "rejected")


# ---------- v2: deadline + urgency ----------
def test_urgency_buckets():
    assert urgency_for(2) == "urgent"
    assert urgency_for(6) == "soon"
    assert urgency_for(30) == "info"


def test_urgency_only_on_outstanding_items():
    p = mock_data.get_profile("4")
    r = build_checklist(p, today=date(2026, 5, 31))  # deadline 2026-06-03 (3 days)
    assert _item(r, "transcript").urgency == "urgent"   # rejected -> outstanding
    assert _item(r, "cv").urgency is None               # verified -> not outstanding
    assert _item(r, "cv").deadline == "2026-06-03"      # deadline still shown


def test_explanations_batched_into_one_llm_call(monkeypatch):
    # Perf: all item explanations come from a SINGLE explain_map call, not N.
    calls = {"n": 0}

    def fake_map(system, user, fallback):
        calls["n"] += 1
        return fallback

    monkeypatch.setattr("agents.checklist.agent.llm.explain_map", fake_map)
    resp = handle(mock_data.get_profile("4"), {"today": "2026-05-31"})
    assert resp.status == "ok"
    assert calls["n"] == 1  # one batched call regardless of item count


def test_handle_today_injection_and_outstanding_summary():
    p = mock_data.get_profile("4")
    resp = handle(p, {"today": "2026-05-31"})
    assert resp.status == "ok"
    assert resp.data["outstanding_count"] >= 1
    assert "待处理" in resp.speakable
    # rich fields surfaced
    assert all("status_label" in it and "urgency" in it for it in resp.data["items"])
