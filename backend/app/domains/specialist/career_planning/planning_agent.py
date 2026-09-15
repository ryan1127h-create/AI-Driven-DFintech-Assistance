"""LLM writer and deterministic fallback for independent career planning."""

from __future__ import annotations

import json
import re

from app.adapters.deepseek_adapter import llm


_MAX_TOKENS = 5000
_VALID_STATUSES = {"has", "partial", "missing", "unknown"}
_ACADEMIC_REFERENCE = re.compile(
    r"\b(?:course|courses|module|modules|curriculum|elective|nusmods)\b"
    r"|\b[A-Z]{2,4}\d{4}[A-Z]?\b"
    r"|(?:课程|选修课|必修课|课程代码|模块)",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
You are the Career Planning Advisor for the NUS Master of Science in
Digital Financial Technology (MSc DFT) programme.

Create a practical career-readiness plan from the supplied career evidence
and career-reference material ONLY. Do not use prior knowledge or invent
skills, employers, salaries, credentials, or outcomes.

Hard rules:
- The response is about role readiness, work evidence, portfolio evidence,
  networking, interviews, and job-search milestones.
- Never recommend or name academic courses, modules, electives, course codes,
  curricula, or study plans. This prohibition applies even if the reference
  material contains them.
- For each capability, use exactly one status: has, partial, missing, unknown.
  Absence of evidence means unknown, not missing. Use missing only when the
  supplied profile explicitly establishes that the capability is absent.
- current_fit: 2-4 evidence-based sentences. State limits plainly.
- skill_assessment: up to 7 role-relevant capabilities, each with a short
  evidence statement. An empty list is valid when requirements are unavailable.
- phases: 2-3 ordered phases. Each phase needs a name, timeframe, 2-4 concrete
  actions, and 1-3 observable success indicators.
- success_indicators: 2-5 overall indicators that show increasing job readiness.
- The guidance is advisory. Never promise employment outcomes.
- Reply with ONLY a valid JSON object, no markdown fences:
{"current_fit": "...", "skill_assessment": [
  {"skill": "...", "status": "unknown", "evidence": "..."}],
 "phases": [{"name": "...", "timeframe": "...", "actions": ["..."],
  "success_indicators": ["..."]}],
 "success_indicators": ["..."], "notes": ["optional caveats"]}
"""


def contains_academic_reference(value: object) -> bool:
    """Return True when visible plan content contains an academic recommendation."""
    if isinstance(value, dict):
        return any(contains_academic_reference(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_academic_reference(item) for item in value)
    return isinstance(value, str) and bool(_ACADEMIC_REFERENCE.search(value))


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))][:limit]


def _parse_plan(parsed: object) -> dict | None:
    if not isinstance(parsed, dict):
        return None

    assessments = []
    raw_assessments = parsed.get("skill_assessment", [])
    if isinstance(raw_assessments, list):
        for item in raw_assessments[:7]:
            if not isinstance(item, dict):
                continue
            skill = _text(item.get("skill"))
            status = _text(item.get("status")).lower()
            evidence = _text(item.get("evidence"))
            if skill and status in _VALID_STATUSES and evidence:
                assessments.append({"skill": skill, "status": status, "evidence": evidence})

    phases = []
    raw_phases = parsed.get("phases", [])
    if isinstance(raw_phases, list):
        for item in raw_phases[:3]:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            timeframe = _text(item.get("timeframe"))
            actions = _text_list(item.get("actions"), 4)
            indicators = _text_list(item.get("success_indicators"), 3)
            if name and timeframe and actions and indicators:
                phases.append(
                    {
                        "name": name,
                        "timeframe": timeframe,
                        "actions": actions,
                        "success_indicators": indicators,
                    }
                )

    plan = {
        "current_fit": _text(parsed.get("current_fit")),
        "skill_assessment": assessments,
        "phases": phases,
        "success_indicators": _text_list(parsed.get("success_indicators"), 5),
        "notes": _text_list(parsed.get("notes"), 5),
    }
    if not plan["current_fit"] or not plan["phases"] or not plan["success_indicators"]:
        return None
    if contains_academic_reference(plan):
        print("[career_planning.planning_agent] Warning: academic recommendation detected — falling back")
        return None
    return plan


def write_plan(
    profile_summary: str,
    role_title: str,
    career_context: str,
    timeline: str | None,
    region: str | None,
) -> dict | None:
    user_prompt = (
        f"Career evidence:\n{profile_summary or 'No career evidence on file.'}\n\n"
        f"Target role: {role_title}\n"
        f"Requested timeline: {timeline or 'not specified'}\n"
        f"Region of interest: {region or 'not specified'}\n\n"
        f"Career-reference material:\n{career_context or 'none available'}"
    )

    try:
        content = llm.complete(_SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=_MAX_TOKENS)
        plan = _parse_plan(json.loads(content.strip()))
    except Exception as exc:
        print(f"[career_planning.planning_agent] Warning: LLM plan failed — {exc}")
        return None

    if plan is None:
        print("[career_planning.planning_agent] Warning: incomplete or unsafe LLM plan — falling back")
    return plan


def fallback_plan(
    role_title: str,
    has_profile: bool,
    timeline: str | None,
    region: str | None,
) -> dict:
    """Conservative plan used when grounded role analysis is unavailable."""
    fit = (
        f"Your profile contains some career evidence, but there is not enough verified role information "
        f"to assess your current fit for {role_title} reliably."
        if has_profile
        else f"There is not enough profile evidence to assess your current fit for {role_title} reliably."
    )
    market = f" in {region}" if region else ""
    horizon = timeline or "the next few months"

    phases = [
        {
            "name": "Evidence baseline",
            "timeframe": "First stage",
            "actions": [
                f"Collect several current {role_title} job descriptions{market} and extract their repeated responsibilities.",
                "Create an evidence inventory linking each responsibility to a work example, project, or measurable result.",
                "Mark every unsupported capability as unknown until you can verify it with evidence.",
            ],
            "success_indicators": [
                "A role-specific responsibility checklist is complete.",
                "Each claimed strength has at least one concrete example.",
            ],
        },
        {
            "name": "Readiness validation",
            "timeframe": horizon,
            "actions": [
                "Build or refine one work sample that demonstrates the most important unproven capability.",
                "Ask a practitioner or mentor to review the evidence inventory and identify the highest-risk gap.",
                "Run role-specific interview practice and record recurring weak areas.",
            ],
            "success_indicators": [
                "A reviewer can trace the main role requirements to concrete evidence.",
                "Interview practice shows fewer repeated weak areas over time.",
            ],
        },
    ]
    return {
        "current_fit": fit,
        "skill_assessment": [],
        "phases": phases,
        "success_indicators": [
            "The evidence inventory covers the role's recurring responsibilities.",
            "At least one relevant work sample is ready to show.",
            "External feedback confirms the next development priority.",
        ],
        "notes": [
            "This conservative plan was used because a grounded, detailed role assessment was unavailable."
        ],
    }
