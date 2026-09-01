"""
Course-recommendation orchestration — the engine behind the
/course-recommendations endpoint (see api.py), kept independent of FastAPI.

Straight-line flow, no branching graph:

    1. resolve the target role
         request > stored profile (via profile.interface)
         standard role (6 known ids)  -> curated skills from career_roles
         any other text               -> LLM maps it to our 9 skill tags
                                         (role_mapper.py, noted in the
                                         response as AI-inferred)
    2. rule_engine.build_candidate_pool()   hard rules, pure code
    3. recommendation_agent.select_courses() LLM picks 6-8 from the pool
         on failure -> rule_engine.score_candidates() deterministic fallback
    4. assemble RecommendationResult         api.py maps it to the schema

Profile access goes through profile.interface only, per the module-
isolation rule.
"""

from __future__ import annotations

from app.domains.course_recommendation import recommendation_agent, role_mapper, rule_engine
from app.domains.course_recommendation import repository
from app.domains.course_recommendation.models import RecommendationResult
from app.domains.profile.interface import get_profile

# The rule set shown to the LLM and cited in `sources`. New students are on
# the 2026-08-onwards curriculum; per-request intake selection is a later
# extension.
_CURRENT_INTAKE = "2026-08-onwards"

_ANNEX_SOURCE = "Annex A curriculum structure"
_CAREER_MAP_SOURCE = "Career pathway mapping — compiled by this project, not official NUS content"


def recommend_courses(
    user_id: str | None = None,
    target_role: str | None = None,
    completed_courses: list[str] | None = None,
    preferences: list[str] | None = None,
) -> RecommendationResult:
    preferences = preferences or []
    notes: list[str] = []

    # 1. Fill what the request left blank from the stored profile: the
    # target role, and the completed courses (prior/background courses the
    # resume mentioned — codes get matched, titles are reported as
    # unrecognized).
    profile = None
    if target_role is None or not completed_courses:
        profile = (get_profile(user_id) if user_id else None) or {}

    role_text = target_role if target_role is not None else profile.get("target_role_std")
    if not completed_courses:
        completed_courses = profile.get("completed_courses") or []
        if completed_courses:
            notes.append("Completed courses were taken from your profile.")

    role_title, role_skills = _resolve_role_skills(role_text, notes)

    # 2. Hard rules build the pool (pure code).
    courses = repository.load_courses()
    pool = rule_engine.build_candidate_pool(courses, completed_courses, role_skills)
    notes.extend(pool.notes)

    # 3. LLM picks from the pool; deterministic ranking is the fallback.
    rules = [r for r in repository.load_curriculum_rules() if r.intake == _CURRENT_INTAKE]
    selection = recommendation_agent.select_courses(pool, rules, role_title, preferences)

    if selection is not None:
        picks, agent_notes = selection
        notes.extend(agent_notes)
    else:
        picks = _fallback_picks(pool, role_skills, preferences)
        notes.append(
            "Courses were selected by deterministic rules: the language "
            "model selector was unavailable for this request."
        )

    # 4. Assemble the response (matched_skills always computed by code).
    by_code = {c.code: c for c in pool.eligible}
    recommendations = tuple(
        {
            "course_code": p["course_code"],
            "course_title": by_code[p["course_code"]].title,
            "units": by_code[p["course_code"]].units,
            "section": by_code[p["course_code"]].section,
            "priority": p["priority"],
            "matched_skills": rule_engine.matched_skills_of(by_code[p["course_code"]], role_skills),
            "reason": p["reason"],
        }
        for p in picks
    )

    return RecommendationResult(
        target_role=role_title,
        recommendations=recommendations,
        skill_gaps=pool.skill_gaps,
        completed_recognized=pool.completed_recognized,
        completed_unrecognized=pool.completed_unrecognized,
        completed_units=pool.completed_units,
        notes=tuple(notes),
        sources=_sources_for(recommendations, role_skills),
    )


def _resolve_role_skills(role_text: str | None, notes: list[str]) -> tuple[str | None, list[str]]:
    """Standard role -> curated skills; free text -> LLM mapping (noted);
    nothing/failed -> no role-based matching (noted)."""
    if not role_text or not role_text.strip():
        notes.append(
            "No target role provided (request or profile) — recommendations "
            "are not role-matched. Set a target role for better results."
        )
        return None, []

    role_text = role_text.strip()
    standard = repository.load_career_roles().get(role_text)
    if standard is not None:
        return standard.role_title, list(standard.required_skills)

    skills = role_mapper.map_role_to_skills(role_text)
    if skills is None:
        notes.append(
            f"Could not map the role '{role_text}' to known skills — "
            "recommendations are not role-matched. Try one of the standard "
            "roles: " + ", ".join(sorted(repository.load_career_roles()))
        )
        return role_text, []

    notes.append(
        f"'{role_text}' is not a standard role in our data — its skill "
        f"needs ({', '.join(skills)}) were inferred by AI as a guide."
    )
    return role_text, skills


def _fallback_picks(pool, role_skills: list[str], preferences: list[str]) -> list[dict]:
    """Deterministic selection used when the LLM is unavailable — same dict
    shape as the LLM's validated picks."""
    scored = rule_engine.score_candidates(pool, role_skills, preferences, pool.completed_recognized)
    picks = []
    for sc in scored:
        evidence = []
        if sc.matched_gap_skills:
            evidence.append("closes skill gaps: " + ", ".join(sc.matched_gap_skills))
        if sc.matched_role_skills:
            evidence.append("covers role-relevant skills: " + ", ".join(sc.matched_role_skills))
        if sc.matched_preferences:
            evidence.append("matches your interests: " + ", ".join(sc.matched_preferences))
        if not evidence:
            evidence.append("part of the Core Courses required of every student")
        picks.append({
            "course_code": sc.course.code,
            "priority": rule_engine.priority_of(sc.score),
            "reason": "; ".join(evidence).capitalize() + ".",
        })
    return picks


def _sources_for(recommendations: tuple[dict, ...], role_skills: list[str]) -> tuple[str, ...]:
    """Annex A + career-mapping disclaimer (when role-matched) + each
    recommended course's NUSMods page, deduplicated."""
    by_code = {c.code: c for c in repository.load_courses()}
    sources = [_ANNEX_SOURCE]
    if role_skills:
        sources.append(_CAREER_MAP_SOURCE)
    seen = set(sources)
    for rec in recommendations:
        url = by_code[rec["course_code"]].source_url
        if url and url not in seen:
            seen.add(url)
            sources.append(url)
    return tuple(sources)
