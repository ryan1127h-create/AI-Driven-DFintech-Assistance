"""Deterministic tests for #4 checklist rule engine (no LLM dependency)."""
from datetime import date

import pytest

from app.agents.checklist.agent import handle
from app.agents.checklist.engine import build_checklist, urgency_for
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


def test_low_classification_adds_academic_justification():
    """`degree_classification_below` must actually reach the output."""
    p = mock_data.get_profile("4")  # second_lower == below 2:1
    item = _item(build_checklist(p), "academic_justification")
    assert item.required is False  # supporting statement, not an official requirement


def test_threshold_classification_is_not_below_threshold():
    p = mock_data.get_profile("5")  # second_upper == the threshold itself
    assert "academic_justification" not in _keys(build_checklist(p))


def test_engine_evaluates_every_condition_the_admin_layer_allows():
    """Drift guard: an authored rule that validates must be evaluable at runtime."""
    from admin.schemas import SUPPORTED_CONDITIONS
    from app.agents.checklist.engine import _CONDITION_EVALUATORS

    assert SUPPORTED_CONDITIONS == set(_CONDITION_EVALUATORS)


# ---------- v3: English proof keyed on medium of instruction ----------
def test_english_medium_institution_waives_proof_despite_nationality():
    # Non-exempt nationality + a degree from a known English-medium institution:
    # the applicant must NOT be told to sit IELTS.
    p = mock_data.get_profile("1")  # country IN
    p.academic_background.institution = "National University of Singapore"
    assert "english_proficiency" not in _keys(build_checklist(p))


def test_unconfirmed_english_proof_does_not_inflate_the_outstanding_count():
    """An unconfirmed requirement is surfaced but must not block: it is not outstanding.

    Compares the same profile with and without a waiver signal: raising the
    "please confirm" item must leave the outstanding count untouched.
    """
    unconfirmed = mock_data.get_profile("1")
    unconfirmed.country = None  # no signal either way; institution not English-medium
    waived = mock_data.get_profile("1")
    waived.country = "SG"  # exempt education system -> item never raised

    r_unconfirmed = build_checklist(unconfirmed, today=date(2026, 6, 1))
    r_waived = build_checklist(waived, today=date(2026, 6, 1))

    assert "english_proficiency" in _keys(r_unconfirmed)  # surfaced, not dropped
    assert "english_proficiency" not in _keys(r_waived)
    item = _item(r_unconfirmed, "english_proficiency")
    assert item.required is False  # cannot be asserted from missing data
    assert r_unconfirmed.outstanding_count == 5
    assert r_waived.outstanding_count == 5


def test_a_conditional_item_is_not_flattened_into_optional_supporting_material():
    """`conditional` (unresolved) and `supporting` (genuinely optional) differ.

    Both are non-blocking, so a single `required` boolean cannot tell them apart —
    and the difference is what stops the system claiming an application is
    complete while an unresolved requirement is still open.
    """
    r = build_checklist(mock_data.get_profile("1"))  # country IN -> medium unknown
    assert _item(r, "english_proficiency").requirement == "conditional"
    assert _item(r, "standardised_test_scores").requirement == "supporting"
    assert _item(r, "transcript").requirement == "required"


def test_a_conditional_item_asks_the_applicant_to_confirm_it():
    """The honesty of `conditional` rests on the copy the applicant actually reads.

    The item is kept out of the outstanding count precisely because the engine
    cannot tell whether it applies; copy that asserted the requirement would tell
    the applicant to sit an exam we have no grounds to demand.
    """
    item = _item(build_checklist(mock_data.get_profile("1")), "english_proficiency")
    assert item.requirement == "conditional"
    assert "confirm" in item.why.lower()


@pytest.mark.parametrize("level", ["optional", None])
def test_unmappable_requirement_level_is_rejected_rather_than_guessed(monkeypatch, level):
    """The rules file is authored, partly by the admin LLM pipeline.

    Its pydantic schema does not model `requirement`, so an edit that drops the
    key (None) or invents a synonym ("optional") reaches the engine unchallenged.
    Either must fail loudly rather than silently re-classify a document.
    """
    from app.agents.checklist import engine

    rules = engine._load_rules()
    if level is None:
        rules["base_items"][0].pop("requirement")
    else:
        rules["base_items"][0]["requirement"] = level
    monkeypatch.setattr(engine, "_load_rules", lambda: rules)

    with pytest.raises(ValueError, match="unknown requirement level"):
        build_checklist(mock_data.get_profile("1"))


def test_english_proof_waived_for_exempt_education_system():
    p = mock_data.get_profile("2")  # country SG, no institution on record
    assert "english_proficiency" not in _keys(build_checklist(p))


# ---------- v3: only a document-submission deadline may reach an item ----------
def test_document_deadline_is_used_when_it_is_the_only_one():
    p = mock_data.get_profile("3")  # only document_deadline: 2026-06-10
    item = _item(build_checklist(p, today=date(2026, 6, 5)), "transcript")
    assert item.deadline == "2026-06-10"
    assert item.urgency == "soon"  # 5 days left


def test_offer_acceptance_date_is_never_shown_as_a_document_deadline():
    """Profile 1's only date is offer_acceptance 2026-07-15 — a different kind of date.

    Replying to an offer is not a document submission, so no item (least of all
    "Application Fee Payment", already paid at UNDER_REVIEW) may claim it. With
    no document deadline on record the honest output is no deadline at all.
    """
    p = mock_data.get_profile("1")
    r = build_checklist(p, today=date(2026, 7, 14))  # 1 day before offer_acceptance
    assert all(it.deadline is None for it in r.items)
    assert all(it.urgency is None for it in r.items)


def test_application_deadline_wins_over_an_unrelated_offer_acceptance_date():
    p = mock_data.get_profile("5")  # application_deadline 2026-06-05 + offer_acceptance
    assert _item(build_checklist(p, today=date(2026, 6, 1)), "transcript").deadline == "2026-06-05"


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
    assert urgency_for(-1) == "overdue"  # a date that has gone is not "approaching"
    assert urgency_for(0) == "urgent"
    assert urgency_for(2) == "urgent"
    assert urgency_for(6) == "soon"
    assert urgency_for(30) == "info"


def test_urgency_only_on_outstanding_items():
    p = mock_data.get_profile("4")
    r = build_checklist(p, today=date(2026, 5, 31))  # deadline 2026-06-03 (3 days)
    assert _item(r, "transcript").urgency == "urgent"   # rejected -> outstanding
    assert _item(r, "cv").urgency is None               # verified -> not outstanding
    assert _item(r, "cv").deadline == "2026-06-03"      # deadline still shown
    # An optional item is never urgent: we only chase what we actually require.
    assert _item(r, "standardised_test_scores").urgency is None  # missing but required=False


def test_explanations_batched_into_one_llm_call(monkeypatch):
    # Perf: all item explanations come from a SINGLE explain_map call, not N.
    calls = {"n": 0}

    def fake_map(system, user, fallback):
        calls["n"] += 1
        return fallback

    monkeypatch.setattr("app.agents.checklist.agent.llm.explain_map", fake_map)
    resp = handle(mock_data.get_profile("4"), {"today": "2026-05-31"})
    assert resp.status == "ok"
    assert calls["n"] == 1  # one batched call regardless of item count


def test_handle_outstanding_summary_and_rich_fields():
    p = mock_data.get_profile("4")
    resp = handle(p, {"today": "2026-05-31"})
    assert resp.status == "ok"
    assert resp.data["outstanding_count"] >= 1
    assert f"You still have {resp.data['outstanding_count']} item(s) to handle" in resp.speakable
    # rich fields surfaced
    assert all(
        {"status_label", "urgency", "requirement"} <= set(it) for it in resp.data["items"]
    )


def test_handle_uses_the_injected_today_and_not_the_wall_clock():
    """`slots["today"]` must drive every date-derived field, or tests lie about time."""
    p = mock_data.get_profile("4")  # application_deadline 2026-06-03

    def urgency(today: str) -> str | None:
        resp = handle(p, {"today": today})
        return next(it["urgency"] for it in resp.data["items"] if it["key"] == "transcript")

    assert urgency("2026-05-01") == "info"      # 33 days left
    assert urgency("2026-06-01") == "urgent"    # 2 days left
    assert urgency("2026-07-01") == "overdue"   # 28 days past


def test_status_labels_reach_the_response():
    resp = handle(mock_data.get_profile("4"), {"today": "2026-05-31"})
    labels = {it["key"]: it["status_label"] for it in resp.data["items"]}
    assert labels["cv"] == "Verified"
    assert labels["transcript"] == "Rejected"
    assert labels["personal_statement"] == "Under review"
    assert labels["referee_reports"] == "To prepare"


def test_a_past_due_deadline_is_not_announced_as_close_to_the_deadline():
    """Profile 4's deadline is 2026-06-03; a month later it has passed, not neared."""
    late = handle(mock_data.get_profile("4"), {"today": "2026-07-01"})
    assert "close to the deadline" not in late.speakable
    assert "The deadline for" in late.speakable and "2026-06-03" in late.speakable


def test_all_materials_present_is_only_claimed_when_nothing_is_unresolved():
    """Completeness is a claim like any other: it needs the data to support it.

    Both applicants have submitted every item we can confirm as required. Only the
    one whose medium of instruction is on record (via the exempt education system)
    may be told the materials are complete.
    """
    resolved = mock_data.get_profile("1")
    resolved.country = "SG"  # exempt -> the conditional item is never raised
    unresolved = mock_data.get_profile("1")  # country IN -> medium of instruction unknown
    for p in (resolved, unresolved):
        p.application.submitted_documents = [
            it.key for it in build_checklist(p).items if it.required
        ]

    done = handle(resolved, {"today": "2026-06-01"})
    still_open = handle(unresolved, {"today": "2026-06-01"})

    assert done.data["outstanding_count"] == 0
    assert still_open.data["outstanding_count"] == 0
    assert "All required application materials are present" in done.speakable
    assert "All required application materials are present" not in still_open.speakable
    assert "TOEFL / IELTS Score Report" in still_open.speakable


def test_speakable_only_claims_a_deadline_the_profile_records():
    """The reported symptom of the deadline misattribution was a spoken warning.

    Profile 1 records only an `offer_acceptance` date, so the summary must name no
    deadline at all; profile 4 records a real `application_deadline`, so the same
    code path must still warn.
    """
    silent = handle(mock_data.get_profile("1"), {"today": "2026-07-14"})
    assert "2026-07-15" not in silent.speakable
    assert "deadline" not in silent.speakable

    warned = handle(mock_data.get_profile("4"), {"today": "2026-05-31"})
    assert "close to the deadline (2026-06-03)" in warned.speakable


def test_speakable_uses_english_punctuation():
    resp = handle(mock_data.get_profile("4"), {"today": "2026-05-31"})
    assert "、" not in resp.speakable  # Chinese enumeration comma must not appear
    assert ", " in resp.speakable  # multiple outstanding labels joined in English


def test_llm_prompt_asks_for_english_output():
    """Prompt language must match the offline fallback template (English)."""
    from app.agents.checklist.agent import _SYSTEM

    assert "English" in _SYSTEM
    assert "Chinese" not in _SYSTEM
