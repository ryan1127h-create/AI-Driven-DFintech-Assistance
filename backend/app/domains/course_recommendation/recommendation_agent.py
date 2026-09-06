"""
Course selector — the LLM picks WHICH courses to recommend.

Division of labour: the rule engine has already decided which courses are
ELIGIBLE (completed/precluded/non-recommendable courses are gone). This agent
selects up to the requested limit, sets each priority, and writes the reason.
Code then validates the picks: any course code not in the pool is dropped,
and if fewer than MIN_VALID_PICKS survive
the whole selection is treated as failed and the caller (service.py) falls
back to the deterministic ranking — so the endpoint always answers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.domains.course_recommendation.errors import ErrorCode
from app.domains.course_recommendation.models import (
    CandidatePool,
    CurriculumRule,
    SelectionPick,
)

logger = get_logger(__name__)

# Below this many valid picks the LLM answer is considered unusable.
MIN_VALID_PICKS = 3

_VALID_PRIORITIES = {"high", "medium", "low"}
_MAX_REASON_LENGTH = 1000

# Generous headroom above the visible JSON as a safety margin against truncation.
_MAX_TOKENS = 4000

_SYSTEM_PROMPT = """\
You are a course recommendation advisor.

From the ELIGIBLE COURSES list below, choose the courses that best fit this
student, give each a priority (high / medium / low), and write a short reason
(1-2 sentences) per course. Obey the selection limit in the user message.

Hard rules:
- Only pick course codes that appear in the ELIGIBLE COURSES list. Never
  invent, merge, or rename courses.
- Base reasons on the supplied facts (skills, sections, descriptions,
  curriculum rules) — no outside knowledge, no invented figures.
- Prefer courses that close the student's skill gaps and match their stated
  preferences. Apply only the curriculum rules supplied in the user message.
- Treat the supplied role profile as guidance, not academic policy. Phrase
  role-fit reasons as suggestions, never as requirements or guarantees.
- Reply with ONLY a valid JSON object, no markdown fences:
{"recommendations": [{"course_code": "FT5005", "priority": "high",
  "reason": "..."}], "notes": ["optional overall advice"]}
"""


@dataclass(frozen=True)
class SelectionOutcome:
    picks: tuple[SelectionPick, ...] | None
    notes: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False


def _pool_block(pool: CandidatePool) -> str:
    """One compact line per eligible course — everything the LLM may use."""
    lines = []
    for c in pool.eligible:
        lines.append(
            f"- {c.code} | {c.title} | {c.units} units "
            f"| section: {c.section or 'not supplied'} "
            f"| skills: {', '.join(c.skills) or 'none'} "
            f"| offered terms: {', '.join(c.offered_terms) or 'not supplied'} "
            f"| course time: {c.course_time or 'not supplied'} "
            f"| prerequisites: {c.prerequisite_text or 'none'} "
            f"| {c.description[:220]}"
        )
    return "\n".join(lines)


def _user_prompt(
    pool: CandidatePool,
    rules: list[CurriculumRule],
    role_title: str | None,
    preferences: list[str],
    student_context: list[str] | None,
    selection_limit: int,
) -> str:
    rules_text = (
        "\n".join(
            f"- [{rule.category} | {rule.intake} | {rule.rule_key}] {rule.text}"
            for rule in rules
        )
        or "none supplied"
    )
    context_text = (
        "\n".join(f"- {fact}" for fact in student_context or []) or "none supplied"
    )
    return (
        "Student context:\n"
        f"- target role: {role_title or 'not specified'}\n"
        f"- stated preferences: {', '.join(preferences) or 'none'}\n"
        f"- completed courses: {', '.join(pool.completed_recognized) or 'none'}\n"
        f"- completed units so far: {pool.completed_units}\n"
        f"- skill gaps for the role: {', '.join(pool.skill_gaps) or 'none'}\n"
        f"- selection limit: {selection_limit}\n"
        f"Additional structured background:\n{context_text}\n\n"
        f"Curriculum rules supplied by the upstream agent:\n{rules_text}\n\n"
        f"ELIGIBLE COURSES (pick only from these):\n{_pool_block(pool)}"
    )


def _invalid_model_response(request_id: str, log_message: str) -> SelectionOutcome:
    logger.warning(
        "%s request_id=%s code=%s",
        log_message,
        request_id,
        ErrorCode.LLM_RESPONSE_INVALID,
    )
    return SelectionOutcome(
        picks=None,
        error_code=ErrorCode.LLM_RESPONSE_INVALID,
        error_message="The course-selection model returned an invalid response.",
        retryable=True,
    )


def _parse_selection(
    content: str,
    pool: CandidatePool,
    selection_limit: int,
    request_id: str,
) -> SelectionOutcome:
    try:
        parsed = json.loads(content.strip())
    except (AttributeError, json.JSONDecodeError, TypeError):
        return _invalid_model_response(
            request_id,
            "course selection returned malformed JSON",
        )

    if not isinstance(parsed, dict):
        return _invalid_model_response(
            request_id,
            "course selection returned a non-object payload",
        )

    raw_picks = parsed.get("recommendations", [])
    raw_notes = parsed.get("notes", [])
    if not isinstance(raw_picks, list) or not isinstance(raw_notes, list):
        return _invalid_model_response(
            request_id,
            "course selection returned invalid field types",
        )

    picks = validate_picks(
        raw_picks,
        pool,
        max_picks=selection_limit,
        min_valid_picks=min(MIN_VALID_PICKS, selection_limit),
    )
    if picks is None:
        logger.warning(
            "too few valid course selections request_id=%s code=%s",
            request_id,
            ErrorCode.LLM_SELECTION_INSUFFICIENT,
        )
        return SelectionOutcome(
            picks=None,
            error_code=ErrorCode.LLM_SELECTION_INSUFFICIENT,
            error_message="Too few valid model selections passed rule validation.",
            retryable=True,
        )

    notes = tuple(
        note.strip() for note in raw_notes if isinstance(note, str) and note.strip()
    )
    return SelectionOutcome(picks=tuple(picks), notes=notes)


def select_courses(
    pool: CandidatePool,
    rules: list[CurriculumRule],
    role_title: str | None,
    preferences: list[str],
    student_context: list[str] | None = None,
    *,
    max_picks: int,
    request_id: str,
) -> SelectionOutcome:
    """
    Ask the LLM to pick and explain courses. The typed outcome records the
    exact reason when the caller must use deterministic fallback.
    """
    if not pool.eligible:
        return SelectionOutcome(picks=())

    selection_limit = min(max_picks, len(pool.eligible))
    if selection_limit <= 0:
        return SelectionOutcome(picks=())

    user_prompt = _user_prompt(
        pool,
        rules,
        role_title,
        preferences,
        student_context,
        selection_limit,
    )

    try:
        content = llm.complete(
            _SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=_MAX_TOKENS
        )
    except Exception:
        logger.exception(
            "course selection failed request_id=%s code=%s",
            request_id,
            ErrorCode.LLM_SELECTION_FAILED,
        )
        return SelectionOutcome(
            picks=None,
            error_code=ErrorCode.LLM_SELECTION_FAILED,
            error_message="The course-selection model was unavailable.",
            retryable=True,
        )
    return _parse_selection(content, pool, selection_limit, request_id)


def validate_picks(
    raw_picks: list[object],
    pool: CandidatePool,
    *,
    max_picks: int,
    min_valid_picks: int,
) -> list[SelectionPick] | None:
    """Code-side check of the LLM's answer: drop unknown/duplicate codes and
    bad priorities, enforce the request limit, and reject sparse output."""
    eligible_codes = {c.code for c in pool.eligible}
    picks: list[SelectionPick] = []
    seen: set[str] = set()

    for item in raw_picks:
        if not isinstance(item, dict):
            continue
        code = str(item.get("course_code", "")).strip().upper()
        if code not in eligible_codes or code in seen:
            continue  # hallucinated or duplicate — silently dropped
        priority = str(item.get("priority", "")).strip().lower()
        reason = str(item.get("reason", "")).strip()
        if (
            priority not in _VALID_PRIORITIES
            or not reason
            or len(reason) > _MAX_REASON_LENGTH
        ):
            continue
        seen.add(code)
        picks.append({"course_code": code, "priority": priority, "reason": reason})
        if len(picks) >= max_picks:
            break

    if len(picks) < min_valid_picks:
        return None
    return picks
