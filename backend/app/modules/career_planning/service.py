"""
Career-planning orchestration — the engine behind the /career-plans
endpoint (see api.py), kept independent of FastAPI.

Straight-line flow, everything factual is computed elsewhere and reused:

    1. profile           via profile.interface (read-only)
    2. gaps + courses    via course_recommendation.interface — the ONE
                         implementation of role->skills->courses; this
                         module never re-computes them
    3. career context    via the shared rag_service (career chunks only)
    4. narrative         agents/planning_agent.py writes the plan;
                         deterministic fallback if the LLM is unavailable
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.career_planning.agents import planning_agent
from app.modules.course_recommendation.interface import recommend_courses
from app.modules.profile.interface import TEST_USER_ID, get_profile_summary_text
from app.services.rag_service import cited_sources, retrieve

# How many recommended courses the plan includes (the top of the
# recommendation, which is already priority-ordered).
_MAX_PLAN_COURSES = 5

_CAREER_MAP_SOURCE = "Career pathway mapping — compiled by this project, not official NUS content"


@dataclass(frozen=True)
class CareerPlanResult:
    """What create_career_plan() returns to api.py / interface.py."""
    target_role: str | None
    current_fit: str
    skill_gaps: tuple[str, ...]
    recommended_courses: tuple[dict, ...]
    short_term_actions: tuple[str, ...]
    medium_term_actions: tuple[str, ...]
    notes: tuple[str, ...]
    sources: tuple[str, ...]


def create_career_plan(
    user_id: str | None = None,
    target_role: str | None = None,
    timeline: str | None = None,
    region: str | None = None,
) -> CareerPlanResult:
    uid = user_id or TEST_USER_ID

    # 1-2. Profile + the recommendation this plan builds on (role resolution,
    # skill gaps and course picks all happen inside course_recommendation).
    profile_summary = get_profile_summary_text(uid)
    rec = recommend_courses(user_id=uid, target_role=target_role)
    role_title = rec["target_role"]
    skill_gaps = list(rec["skill_gaps"])
    courses = [
        {k: c[k] for k in ("course_code", "course_title", "priority", "reason")}
        for c in rec["recommended_courses"][:_MAX_PLAN_COURSES]
    ]
    notes = list(rec["notes"])

    # 3. Career-track reference text (never raises; empty list on failure).
    hits = retrieve(
        f"career pathway skills courses {role_title or target_role or ''}",
        top_k=3, filter_topics={"career"},
    )
    career_context = "\n\n".join(f"{h.context}\n{h.content}" for h in hits)

    # 4. Narrative — LLM first, deterministic fallback second.
    plan = planning_agent.write_plan(
        profile_summary=profile_summary,
        role_title=role_title,
        skill_gaps=skill_gaps,
        recommended_courses=courses,
        career_context=career_context,
        timeline=timeline,
        region=region,
    )
    if plan is None:
        plan = planning_agent.fallback_plan(
            role_title=role_title,
            skill_gaps=skill_gaps,
            recommended_courses=courses,
            has_profile=bool(profile_summary),
        )
    notes.extend(plan["notes"])

    sources = [_CAREER_MAP_SOURCE]
    sources += [s for s in cited_sources(hits) if s not in sources]

    return CareerPlanResult(
        target_role=role_title,
        current_fit=plan["current_fit"],
        skill_gaps=tuple(skill_gaps),
        recommended_courses=tuple(courses),
        short_term_actions=tuple(plan["short_term_actions"]),
        medium_term_actions=tuple(plan["medium_term_actions"]),
        notes=tuple(notes),
        sources=tuple(sources),
    )
