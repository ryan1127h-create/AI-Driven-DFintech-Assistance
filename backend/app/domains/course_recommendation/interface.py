"""
Public interface of the course_recommendation domain — the only module
other domains (and the orchestrator) are allowed to import from
app.domains.course_recommendation. Everything else in this package
(repository, rule engine, agents, service internals) is private.

Current consumers:
    - program_comparison uses resolve_role_skills() for its personal
      match-score calculation.
    - career_planning uses recommend_courses() so skill-gap and
      course-selection logic isn't duplicated (same implementation, not a
      second calculation).

Usage:
    from app.domains.course_recommendation.interface import recommend_courses
"""

from __future__ import annotations

from dataclasses import asdict

from app.domains.course_recommendation import service

__all__ = ["recommend_courses", "resolve_role_skills"]


def resolve_role_skills(role_text: str | None) -> dict:
    """Maps a target role (standard id or free text) to our skill tags —
    the one shared implementation other domains should use.

    Returns {"role_title": str | None, "skills": list[str], "notes": list[str]}
    (empty skills means role-based matching isn't possible; notes say why)."""
    notes: list[str] = []
    role_title, skills = service._resolve_role_skills(role_text, notes)
    return {"role_title": role_title, "skills": skills, "notes": notes}


def recommend_courses(
    user_id: str | None = None,
    target_role: str | None = None,
    completed_courses: list[str] | None = None,
    preferences: list[str] | None = None,
) -> dict:
    """Runs a recommendation and returns it as a plain dict (same shape as
    the /course-recommendations response body)."""
    result = service.recommend_courses(
        user_id=user_id,
        target_role=target_role,
        completed_courses=completed_courses,
        preferences=preferences,
    )
    # asdict() keeps tuples as tuples — convert to lists so the shape really
    # matches the JSON response body (callers may mutate or validate lists).
    payload = {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(result).items()}
    payload["recommended_courses"] = payload.pop("recommendations")
    return payload
