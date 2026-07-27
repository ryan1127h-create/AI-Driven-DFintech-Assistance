"""#4 Checklist Agent entry point.

handle(profile) -> AgentResponse, following the contract envelope. The rule
engine decides the checklist (items, status, deadline, urgency); the LLM only
rephrases every item's `why` in ONE batched call (deterministic fallback offline).
"""
from __future__ import annotations

from common import llm
from common.envelope import AgentResponse, EscalationRequest
from common.profile import UserProfile

from .engine import build_checklist

_SYSTEM = (
    "You help applicants understand a Master's application checklist. You are "
    "given a JSON object mapping each document key to {label, why}. Return a "
    "JSON object mapping the SAME keys to ONE short, friendly Chinese sentence "
    "explaining that document in plain language. Do not invent new requirements. "
    "Output JSON only."
)

_STATUS_LABEL = {
    "missing": "To prepare",
    "submitted": "Submitted",
    "under_review": "Under review",
    "verified": "Verified",
    "rejected": "Rejected",
}


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
            "status": it.status,
            "status_label": _STATUS_LABEL.get(it.status, it.status),
            "why": explanations[it.key],
            "deadline": it.deadline,
            "urgency": it.urgency,
        }
        for it in result.items
    ]

    outstanding = [it for it in result.items if it.required and it.status in ("missing", "rejected")]
    if outstanding:
        labels = "、".join(it.label for it in outstanding)
        speakable = f"You still have {len(outstanding)} item(s) to handle: {labels}."
        urgent = [it for it in outstanding if it.urgency == "urgent"]
        if urgent:
            speakable += f" {urgent[0].label} is close to the deadline ({urgent[0].deadline}); please handle it as soon as possible."
    else:
        speakable = "All required application materials are present. The demo will proceed to material completeness checking; real submission must still be completed in the NUS Graduate Admission System."

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
