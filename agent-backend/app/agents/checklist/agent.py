"""#4 Checklist Agent entry point.

handle(profile) -> AgentResponse, following the contract envelope. The rule
engine decides the checklist (items, status, deadline, urgency); the LLM only
rephrases every item's `why` in ONE batched call (deterministic fallback offline).
"""
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse, EscalationRequest
from common.profile import UserProfile

from .engine import REQUIREMENT_CONDITIONAL, build_checklist

_SYSTEM = (
    "You help applicants understand a Master's application checklist. You are "
    "given a JSON object mapping each document key to {label, why}. Return a "
    "JSON object mapping the SAME keys to ONE short, friendly English sentence "
    "explaining that document in plain language. Do not invent new requirements. "
    "Output JSON only."
)

_LABEL_SEPARATOR = ", "  # output is English: no Chinese enumeration comma

_STATUS_LABEL = {
    "missing": "To prepare",
    "submitted": "Submitted",
    "under_review": "Under review",
    "verified": "Verified",
    "rejected": "Rejected",
}

_OUTSTANDING_STATUSES = ("missing", "rejected")

# One sentence per urgency bucket that is worth speaking about. A past-due date
# must not be described as "close to the deadline": the profile records that the
# date has gone, not that it is approaching.
_DEADLINE_SENTENCES = {
    "urgent": "{label} is close to the deadline ({deadline}); please handle it as soon as possible.",
    "overdue": "The deadline for {label} ({deadline}) has already passed.",
}

_ALL_PRESENT = (
    "All required application materials are present. The demo will proceed to material "
    "completeness checking; real submission must still be completed in the NUS Graduate "
    "Admission System."
)


def _deadline_sentence(items) -> str:
    """Warn about the deadline only in the terms the recorded date supports."""
    flagged = next((it for it in items if it.urgency in _DEADLINE_SENTENCES), None)
    if flagged is None:
        return ""
    template = _DEADLINE_SENTENCES[flagged.urgency]
    return " " + template.format(label=flagged.label, deadline=flagged.deadline)


def _summarise(outstanding: list, unresolved: list) -> str:
    """Spoken summary. Completeness is only claimed when nothing is unresolved."""
    if outstanding:
        labels = _LABEL_SEPARATOR.join(it.label for it in outstanding)
        return (
            f"You still have {len(outstanding)} item(s) to handle: {labels}."
            + _deadline_sentence(outstanding)
        )
    if unresolved:
        labels = _LABEL_SEPARATOR.join(it.label for it in unresolved)
        return (
            f"Every item we can confirm as required is present, but {len(unresolved)} "
            f"item(s) depend on details your profile does not record: {labels}. Please "
            "confirm whether they apply to you before treating the application as complete."
        )
    return _ALL_PRESENT


def _explain_all(items) -> dict[str, str]:
    """One batched LLM call for all item explanations; offline -> template why."""
    import json

    fallback = {it.key: it.why for it in items}
    user = json.dumps(
        {it.key: {"label": it.label, "why": it.why} for it in items},
        ensure_ascii=False,
    )
    return llm.explain_map(_SYSTEM, user, fallback)


def handle(profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    if profile.academic_background is None:
        return AgentResponse.needs(
            ["academic_background"],
            "To generate your application checklist, I first need your academic background (degree level and major).",
        )

    from datetime import date

    today = date.fromisoformat(slots["today"]) if slots.get("today") else None
    result = build_checklist(profile, today=today)

    if result.unknown_condition:
        esc = EscalationRequest(
            source_agent="checklist",
            reason="exception_case",
            confidence=0.3,
            user_id=profile.user_id,
            lifecycle_stage=profile.lifecycle_stage,
            conversation_summary=(
                f"Checklist rule referenced an unevaluable condition "
                f"'{result.unknown_condition}'."
            ),
            structured_context={"unknown_condition": result.unknown_condition},
            suggested_routing="admissions_office",
        )
        return AgentResponse(
            status="escalated",
            answer_type="official",
            speakable="Your case requires further confirmation by admissions staff, so I have prepared it for human handling.",
            escalation=esc,
        )

    explanations = _explain_all(result.items)
    items_data = [
        {
            "key": it.key,
            "label": it.label,
            "required": it.required,
            "requirement": it.requirement,
            "status": it.status,
            "status_label": _STATUS_LABEL.get(it.status, it.status),
            "why": explanations[it.key],
            "deadline": it.deadline,
            "urgency": it.urgency,
        }
        for it in result.items
    ]

    outstanding = [it for it in result.items
                   if it.required and it.status in _OUTSTANDING_STATUSES]
    # Conditional items are not blocking, but they are not settled either: the
    # application cannot be called complete while one is still open.
    unresolved = [it for it in result.items
                  if it.requirement == REQUIREMENT_CONDITIONAL
                  and it.status in _OUTSTANDING_STATUSES]
    speakable = _summarise(outstanding, unresolved)

    return AgentResponse(
        status="ok",
        answer_type="official",  # checklist is policy-grounded
        speakable=speakable,
        data={
            "items": items_data,
            "missing_count": result.missing_count,
            "outstanding_count": result.outstanding_count,
        },
        sources=["admissions_rules"],
    )
