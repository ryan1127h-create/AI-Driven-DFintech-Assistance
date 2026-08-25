"""
Course selector — the LLM picks WHICH courses to recommend.

Division of labour: the rule engine has already decided who is ELIGIBLE
(the candidate pool — completed/precluded/non-recommendable courses are
gone). This agent chooses 6-8 courses from that pool, sets each one's
priority, and writes the reason. Code then validates the picks: any course
code not in the pool is dropped, and if fewer than MIN_VALID_PICKS survive
the whole selection is treated as failed and the caller (service.py) falls
back to the deterministic ranking — so the endpoint always answers.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.deepseek_client import build_chat_llm
from app.modules.course_recommendation.models import CandidatePool, CurriculumRule

# Below this many valid picks the LLM answer is considered unusable.
MIN_VALID_PICKS = 3
MAX_PICKS = 8

_VALID_PRIORITIES = {"high", "medium", "low"}

# Generous headroom above the visible JSON as a safety margin against truncation.
_MAX_TOKENS = 4000

_SYSTEM_PROMPT = """\
You are the Course Recommendation Advisor for the NUS Master of Science in
Digital Financial Technology (MSc DFT) programme.

From the ELIGIBLE COURSES list below, choose the 6 to 8 courses that best
fit this student, give each a priority (high / medium / low), and write a
short reason (1-2 sentences) per course.

Hard rules:
- Only pick course codes that appear in the ELIGIBLE COURSES list. Never
  invent, merge, or rename courses.
- Base reasons on the supplied facts (skills, sections, descriptions,
  curriculum rules) — no outside knowledge, no invented figures.
- Prefer courses that close the student's skill gaps and match their stated
  preferences; respect the curriculum rules (core requirements, level-4000
  elective cap) when choosing.
- The career-skill mapping is guidance compiled by this project, not
  official NUS policy — phrase role-fit reasons as suggestions, never as
  requirements or guarantees.
- Reply with ONLY a valid JSON object, no markdown fences:
{"recommendations": [{"course_code": "FT5005", "priority": "high",
  "reason": "..."}], "notes": ["optional overall advice"]}
"""


def _pool_block(pool: CandidatePool) -> str:
    """One compact line per eligible course — everything the LLM may use."""
    lines = []
    for c in pool.eligible:
        lines.append(
            f"- {c.code} | {c.title} | {c.units} units | {c.section or 'not in Annex'} "
            f"| skills: {', '.join(c.skills) or 'none'} | {c.description[:220]}"
        )
    return "\n".join(lines)


def select_courses(
    pool: CandidatePool,
    rules: list[CurriculumRule],
    role_title: str | None,
    preferences: list[str],
) -> tuple[list[dict], list[str]] | None:
    """
    Asks the LLM to pick and explain courses from the pool. Returns
    (picks, notes) where each pick is {"course_code", "priority", "reason"},
    or None if the call failed or too few valid picks survived validation —
    the caller then uses the deterministic fallback.
    """
    if not pool.eligible:
        return [], []

    rules_text = "\n".join(f"- {r.text}" for r in rules) or "none supplied"
    user_prompt = (
        f"Student context:\n"
        f"- target role: {role_title or 'not specified'}\n"
        f"- stated preferences: {', '.join(preferences) or 'none'}\n"
        f"- completed courses: {', '.join(pool.completed_recognized) or 'none'}\n"
        f"- completed units so far: {pool.completed_units}\n"
        f"- skill gaps for the role: {', '.join(pool.skill_gaps) or 'none'}\n\n"
        f"Curriculum rules (current intake):\n{rules_text}\n\n"
        f"ELIGIBLE COURSES (pick only from these):\n{_pool_block(pool)}"
    )

    try:
        response = build_chat_llm(temperature=0.2, max_tokens=_MAX_TOKENS).invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = json.loads(content.strip())
    except Exception as exc:
        print(f"[course_recommendation.recommendation_agent] Warning: LLM selection failed — {exc}")
        return None

    picks = validate_picks(parsed.get("recommendations", []), pool)
    if picks is None:
        return None
    notes = [str(n).strip() for n in parsed.get("notes", []) if str(n).strip()]
    return picks, notes


def validate_picks(raw_picks: list, pool: CandidatePool) -> list[dict] | None:
    """Code-side check of the LLM's answer: drop unknown/duplicate codes and
    bad priorities, cap at MAX_PICKS; None if too few picks survive."""
    eligible_codes = {c.code for c in pool.eligible}
    picks: list[dict] = []
    seen: set[str] = set()

    for item in raw_picks:
        if not isinstance(item, dict):
            continue
        code = str(item.get("course_code", "")).strip().upper()
        if code not in eligible_codes or code in seen:
            continue  # hallucinated or duplicate — silently dropped
        priority = str(item.get("priority", "")).strip().lower()
        reason = str(item.get("reason", "")).strip()
        if priority not in _VALID_PRIORITIES or not reason:
            continue
        seen.add(code)
        picks.append({"course_code": code, "priority": priority, "reason": reason})
        if len(picks) >= MAX_PICKS:
            break

    if len(picks) < MIN_VALID_PICKS:
        print(f"[course_recommendation.recommendation_agent] Warning: only {len(picks)} valid picks — falling back")
        return None
    return picks
