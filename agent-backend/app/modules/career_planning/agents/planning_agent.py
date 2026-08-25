"""
Career-plan writer — the module's only LLM step.

All the facts arrive pre-computed: the profile summary, the skill gaps and
recommended courses (from course_recommendation), and career-track source
text (from the shared RAG service). This agent only writes the narrative —
current fit, short-term actions, medium-term actions. Code supplies a
deterministic fallback for each part, so the endpoint answers even when
the LLM is down.

Prompt rules follow the chatbot's career specialist: the career-pathway
mapping is advisory guidance compiled by this project, never an official
NUS placement guarantee — always suggest, never promise outcomes.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.deepseek_client import build_chat_llm

# Generous headroom above the visible JSON as a safety margin against truncation.
_MAX_TOKENS = 5000

_SYSTEM_PROMPT = """\
You are the Career Planning Advisor for the NUS Master of Science in
Digital Financial Technology (MSc DFT) programme.

Write a practical career plan from the supplied facts ONLY — the student's
profile, their skill gaps, the recommended courses, and the career-track
reference text. Do not invent skills, courses, employers, salaries, or
outcomes that are not in the material.

Hard rules:
- current_fit: 2-4 sentences on how the student's background lines up with
  the target role today, honest about gaps.
- short_term_actions: 3-5 concrete actions for roughly the next 6 months
  (courses to start with, skills to build first).
- medium_term_actions: 3-5 actions for after that (capstone direction,
  portfolio, networking) within the requested timeline if one is given.
- This guidance is compiled by this project, not official NUS policy —
  phrase everything as suggestion ("consider...", "typically calls
  for..."), never as a requirement, and never promise employment outcomes.
- Reply with ONLY a valid JSON object, no markdown fences:
{"current_fit": "...", "short_term_actions": ["..."],
 "medium_term_actions": ["..."], "notes": ["optional caveats"]}
"""


def write_plan(
    profile_summary: str,
    role_title: str | None,
    skill_gaps: list[str],
    recommended_courses: list[dict],
    career_context: str,
    timeline: str | None,
    region: str | None,
) -> dict | None:
    """Returns {"current_fit", "short_term_actions", "medium_term_actions",
    "notes"} or None on failure (caller then uses fallback_plan)."""
    courses_text = "\n".join(
        f"- {c['course_code']} {c['course_title']} (priority: {c['priority']}): {c['reason']}"
        for c in recommended_courses
    ) or "none"

    user_prompt = (
        f"Student profile:\n{profile_summary or 'No profile on file.'}\n\n"
        f"Target role: {role_title or 'not specified'}\n"
        f"Requested timeline: {timeline or 'not specified'}\n"
        f"Region of interest: {region or 'not specified'}\n"
        f"Skill gaps for the role: {', '.join(skill_gaps) or 'none identified'}\n\n"
        f"Recommended courses (already selected, do not add others):\n{courses_text}\n\n"
        f"Career-track reference text:\n{career_context or 'none available'}"
    )

    try:
        response = build_chat_llm(temperature=0.3, max_tokens=_MAX_TOKENS).invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = json.loads(content.strip())
    except Exception as exc:
        print(f"[career_planning.planning_agent] Warning: LLM plan failed — {exc}")
        return None

    plan = {
        "current_fit": str(parsed.get("current_fit", "")).strip(),
        "short_term_actions": [str(a).strip() for a in parsed.get("short_term_actions", []) if str(a).strip()],
        "medium_term_actions": [str(a).strip() for a in parsed.get("medium_term_actions", []) if str(a).strip()],
        "notes": [str(n).strip() for n in parsed.get("notes", []) if str(n).strip()],
    }
    if not plan["current_fit"] or not plan["short_term_actions"] or not plan["medium_term_actions"]:
        print("[career_planning.planning_agent] Warning: incomplete LLM plan — falling back")
        return None
    return plan


def fallback_plan(
    role_title: str | None,
    skill_gaps: list[str],
    recommended_courses: list[dict],
    has_profile: bool,
) -> dict:
    """Deterministic plan used when the LLM is unavailable — plain but
    honest, built only from the computed facts."""
    if has_profile:
        fit = (f"Your profile is on file. For the role of {role_title}, the skills "
               f"still to build are: {', '.join(skill_gaps)}." if role_title and skill_gaps
               else "Your profile is on file, but no role-based fit could be computed.")
    else:
        fit = ("No profile on file yet — upload a resume first so the plan can "
               "reflect your actual background.")

    top = [c["course_code"] for c in recommended_courses[:3]]
    short_term = [f"Start with the highest-priority recommended courses: {', '.join(top)}."] if top else []
    short_term += [f"Build the missing skill '{s}' through the matching recommended courses." for s in skill_gaps[:3]]

    return {
        "current_fit": fit,
        "short_term_actions": short_term or ["Set a target role to get an actionable plan."],
        "medium_term_actions": [
            "Revisit this plan after completing the first recommended courses.",
        ],
        "notes": [
            "This plan was assembled by deterministic rules: the language "
            "model writer was unavailable for this request."
        ],
    }
