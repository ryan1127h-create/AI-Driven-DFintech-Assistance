"""
STAGE 5 (second half) — per-slot LLM proposal with a bounded
self-correction loop, falling back to the deterministic scoring order
(scoring.py) when the model is unavailable or still invalid once the
retry budget is spent.

Division of labour: scoring.py has already ranked the candidates. This
module asks the model for `slot.display_count` course codes, ordered
best-first — more than the `slot.required_pick_count` actually needed
(see requirement_slots.py), so the student sees a few real alternatives
instead of one pre-made decision. Code then validates the answer — wrong
count, a code outside the slot, or a hallucinated code all get a
specific, human-readable rejection reason fed straight back to the model
for one more try (see MAX_RETRIES). service.py marks the first
`required_pick_count` of the returned order as the actual recommendation
and the rest as browsable alternatives — this module only produces the
ordered list. Structurally, a cross-slot duplicate cannot occur here:
STAGE 4 already guarantees a course appears in at most one slot's
eligible list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.domains.specialist.course_recommendation.errors import ErrorCode
from app.domains.specialist.course_recommendation.models import (
    RequirementSlot,
    ScoredCourse,
    SelectionPick,
)
from app.domains.specialist.course_recommendation.pipeline import scoring

logger = get_logger(__name__)

# One initial attempt plus up to this many corrective retries.
MAX_RETRIES = 2
MAX_ATTEMPTS = MAX_RETRIES + 1

_MAX_REASON_LENGTH = 500
_MAX_TOKENS = 1200

_SYSTEM_PROMPT = """\
You are a course recommendation advisor filling ONE requirement group at a \
time for an NUS MSc Digital Financial Technology student.

You are given a display count larger than the number of picks actually \
needed — order your reply best-first: the earliest entries are your top \
pick(s) that satisfy the requirement, the remaining entries are good \
alternatives the student can browse instead. The exact split is applied \
by the caller, not by you — just return every entry in your genuine \
best-to-worst order.

Hard rules:
- Return exactly the requested number of course codes, only from the
  ELIGIBLE CANDIDATES list given — never invent, merge, or rename a course.
- Base each reason (1-2 sentences) on the supplied facts (skills, workload,
  curated-shortlist marker) — no outside knowledge, no invented figures.
- If a candidate is marked as a caution (e.g. heavy independent project
  work), you may still include it, but mention the caution honestly.
- Reply with ONLY a valid JSON object, no markdown fences:
{"recommendations": [{"course_code": "FT5005", "reason": "..."}], \
"notes": ["optional overall advice"]}
- If your previous answer was rejected, fix exactly what the rejection
  reason says and return a corrected JSON object in the same shape."""


@dataclass(frozen=True)
class SlotSelectionOutcome:
    picks: tuple[SelectionPick, ...] | None
    notes: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    attempts: int = 0


def _candidate_block(scored: list[ScoredCourse]) -> str:
    lines = []
    for sc in scored:
        course = sc.course
        tags = []
        if sc.curated_match:
            tags.append("curated pick for this role")
        if sc.workload_note:
            tags.append(f"caution: {sc.workload_note}")
        tag_text = f" | {' | '.join(tags)}" if tags else ""
        lines.append(
            f"- {course.code} | {course.title} | {course.units} units "
            f"| skills: {', '.join(course.skills) or 'none'} "
            f"| workload: {course.workload_shape or 'unknown'}{tag_text} "
            f"| {course.description[:200]}"
        )
    return "\n".join(lines)


def _pick_instruction(slot: RequirementSlot) -> str:
    if slot.required_pick_count == 0:
        # A secondary Vertical group (see requirement_slots.py): nothing
        # here is required, every returned entry is an optional,
        # non-binding exploration option — still ask for a genuine
        # best-first order so the more interesting ones surface first.
        return (
            f"None of these are required — return {slot.display_count} good "
            "optional course code(s) for the student to explore, best-first."
        )
    return (
        f"Return exactly {slot.display_count} course code(s), ordered "
        f"best-first: the top {slot.required_pick_count} satisfy the "
        "requirement, the rest are good alternatives."
    )


def _user_prompt(
    slot: RequirementSlot,
    scored: list[ScoredCourse],
    role_title: str | None,
    student_context: list[str] | None,
    rejection_reason: str | None,
) -> str:
    context_text = "\n".join(f"- {fact}" for fact in student_context or []) or "none supplied"
    prompt = (
        f"Requirement group: {slot.label}\n"
        f"{_pick_instruction(slot)}\n"
        f"Target role: {role_title or 'not specified'}\n"
        f"Student context:\n{context_text}\n\n"
        f"ELIGIBLE CANDIDATES, ranked best-fit first (pick only from these):\n"
        f"{_candidate_block(scored)}"
    )
    if rejection_reason:
        prompt += (
            f"\n\nYour previous answer was rejected: {rejection_reason}. "
            "Return a corrected JSON object."
        )
    return prompt


def _rejection_reason(
    raw_picks: list[object], slot: RequirementSlot, eligible_codes: set[str]
) -> str:
    codes = [
        str(item.get("course_code", "")).strip().upper()
        for item in raw_picks
        if isinstance(item, dict)
    ]
    unknown = [c for c in codes if c not in eligible_codes]
    if unknown:
        return f"course code(s) not in the eligible list: {', '.join(unknown)}"
    if len(set(codes)) != len(codes):
        return "duplicate course codes in your answer"
    if len(codes) != slot.display_count:
        return (
            f"you must return exactly {slot.display_count} course code(s), "
            f"you returned {len(codes)}"
        )
    return "one or more entries were missing a valid reason"


def validate_picks(
    raw_picks: list[object], slot: RequirementSlot, eligible_codes: set[str]
) -> list[SelectionPick] | None:
    """Drops hallucinated/duplicate codes and bad entries; returns None
    (never a partial list) unless the exact display count survives
    validation — a partial slot is treated the same as a failed one so the
    retry loop or fallback can produce a complete answer instead. Order is
    preserved: service.py marks the first `required_pick_count` entries of
    the returned list as the actual recommendation."""
    picks: list[SelectionPick] = []
    seen: set[str] = set()
    for item in raw_picks:
        if not isinstance(item, dict):
            continue
        code = str(item.get("course_code", "")).strip().upper()
        if code not in eligible_codes or code in seen:
            continue
        reason = str(item.get("reason", "")).strip()
        if not reason or len(reason) > _MAX_REASON_LENGTH:
            continue
        seen.add(code)
        picks.append({"course_code": code, "reason": reason})
    if len(picks) != slot.display_count:
        return None
    return picks


def select_for_slot(
    slot: RequirementSlot,
    scored: list[ScoredCourse],
    role_title: str | None,
    student_context: list[str] | None,
    *,
    request_id: str,
) -> SlotSelectionOutcome:
    """Runs the bounded self-correction loop for one requirement slot.
    Never raises — every failure path returns a typed outcome the caller
    (service.py) uses to fall back to scoring.py's deterministic order."""
    eligible_codes = {sc.course.code for sc in scored}
    rejection_reason: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        user_prompt = _user_prompt(slot, scored, role_title, student_context, rejection_reason)
        try:
            content = llm.complete(
                _SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=_MAX_TOKENS
            )
        except Exception:
            logger.exception(
                "slot selection LLM call failed request_id=%s slot=%s attempt=%d",
                request_id,
                slot.slot_id,
                attempt,
            )
            return SlotSelectionOutcome(
                picks=None,
                error_code=ErrorCode.SLOT_LLM_SELECTION_FAILED,
                error_message="The course-selection model was unavailable.",
                retryable=True,
                attempts=attempt,
            )

        raw_picks: list[object] | None
        notes: list[object]
        try:
            parsed = json.loads(content.strip())
            raw_picks = parsed.get("recommendations") if isinstance(parsed, dict) else None
            notes = parsed.get("notes", []) if isinstance(parsed, dict) else []
        except (AttributeError, json.JSONDecodeError, TypeError):
            raw_picks = None
            notes = []

        if not isinstance(raw_picks, list):
            rejection_reason = "reply must be a JSON object with a 'recommendations' array"
            if attempt == MAX_ATTEMPTS:
                logger.warning(
                    "slot selection response invalid after retries request_id=%s slot=%s",
                    request_id,
                    slot.slot_id,
                )
                return SlotSelectionOutcome(
                    picks=None,
                    error_code=ErrorCode.SLOT_LLM_RESPONSE_INVALID,
                    error_message="The model returned a malformed response.",
                    retryable=True,
                    attempts=attempt,
                )
            continue

        picks = validate_picks(raw_picks, slot, eligible_codes)
        if picks is not None:
            clean_notes = tuple(n.strip() for n in notes if isinstance(n, str) and n.strip())
            return SlotSelectionOutcome(picks=tuple(picks), notes=clean_notes, attempts=attempt)

        rejection_reason = _rejection_reason(raw_picks, slot, eligible_codes)
        if attempt == MAX_ATTEMPTS:
            logger.warning(
                "slot selection failed validation after retries request_id=%s slot=%s reason=%s",
                request_id,
                slot.slot_id,
                rejection_reason,
            )
            return SlotSelectionOutcome(
                picks=None,
                error_code=ErrorCode.SLOT_VALIDATION_FAILED,
                error_message=(
                    f"The model's selection failed validation after {attempt} attempts: "
                    f"{rejection_reason}."
                ),
                retryable=True,
                attempts=attempt,
            )

    # Unreachable — the loop always returns on its final attempt above.
    return SlotSelectionOutcome(
        picks=None,
        error_code=ErrorCode.SLOT_LLM_SELECTION_FAILED,
        error_message="Selection loop exhausted without a result.",
        retryable=True,
        attempts=MAX_ATTEMPTS,
    )


def fallback_for_slot(slot: RequirementSlot, scored: list[ScoredCourse]) -> list[SelectionPick]:
    """Deterministic selection used when the LLM path failed for this
    slot — same dict shape (and same best-first order) as its validated
    picks, so service.py's "first required_pick_count = recommended"
    split applies identically regardless of which path produced it."""
    chosen = scoring.rank_for_slot(scored, slot.required_pick_count, slot.display_count)

    picks: list[SelectionPick] = []
    for sc in chosen:
        evidence: list[str] = []
        if sc.matched_gap_skills:
            evidence.append("closes skill gaps: " + ", ".join(sc.matched_gap_skills))
        if sc.matched_role_skills:
            evidence.append("covers role-relevant skills: " + ", ".join(sc.matched_role_skills))
        if sc.matched_preferences:
            evidence.append("matches your stated interests: " + ", ".join(sc.matched_preferences))
        if sc.curated_match:
            evidence.append("on the curated shortlist for this role")
        if sc.workload_note:
            evidence.append(sc.workload_note)
        if not evidence:
            evidence.append(f"counts toward {slot.label}")
        picks.append(
            {"course_code": sc.course.code, "reason": "; ".join(evidence).capitalize() + "."}
        )
    return picks
