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

from app.modules.career_planning.agents import planning_agent
from app.modules.career_planning.models import CareerPlanResult
from app.modules.course_recommendation.interface import recommend_courses
from app.modules.profile.interface import TEST_USER_ID, get_profile, render_profile_summary
from app.services.rag_service import cited_sources, retrieve

# How many recommended courses the plan includes — explicitly sorted by
# priority just below before slicing, since the LLM's course selection
# (course_recommendation.agents.recommendation_agent) doesn't guarantee its
# output array is priority-ordered (only the deterministic fallback ranking
# does, by construction). Without this, "top N" could silently drop a
# high-priority course in favour of a low-priority one whenever the LLM
# picked the courses.
_MAX_PLAN_COURSES = 5
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

_CAREER_MAP_SOURCE = "Career pathway mapping — compiled by this project, not official NUS content"


def create_career_plan(
    user_id: str | None = None,
    target_role: str | None = None,
    timeline: str | None = None,
    region: str | None = None,
) -> CareerPlanResult:
    uid = user_id or TEST_USER_ID

    # 1-2. Profile + the recommendation this plan builds on (role resolution,
    # skill gaps and course picks all happen inside course_recommendation).
    # Fetched once here (render_profile_summary is pure, no I/O) and its
    # completed_courses passed through explicitly, so course_recommendation
    # doesn't redundantly re-fetch the same profile itself — it only needs
    # to when target_role and/or completed_courses weren't already resolved
    # by the caller.
    profile = get_profile(uid)
    profile_summary = render_profile_summary(profile)
    completed_courses = (profile or {}).get("completed_courses")
    rec = recommend_courses(user_id=uid, target_role=target_role, completed_courses=completed_courses)
    role_title = rec["target_role"]
    skill_gaps = list(rec["skill_gaps"])
    by_priority = sorted(
        rec["recommended_courses"], key=lambda c: _PRIORITY_ORDER.get(c["priority"], 99)
    )
    courses = [
        {k: c[k] for k in ("course_code", "course_title", "priority", "reason")}
        for c in by_priority[:_MAX_PLAN_COURSES]
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
