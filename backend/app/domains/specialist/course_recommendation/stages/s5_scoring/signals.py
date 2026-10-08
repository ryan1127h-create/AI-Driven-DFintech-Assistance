"""
S5 scoring signals — one function per signal, all collected in SIGNALS.

Each signal looks at one course in a ScoringContext and returns the
ScoreItem it contributes, or None when it doesn't apply. A signal only
fires when its input was actually supplied (no role -> no role-skill
signal; no workload preference -> no project-heavy penalty), so a missing
input never skews a ranking. Weights come from policy/tuning.py.

To add a signal: write one function here, append it to SIGNALS, and give
it a weight in policy/tuning.py. scorer.py needs no change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.domains.specialist.course_recommendation.models import Course, ScoreItem
from app.domains.specialist.course_recommendation.policy import tuning

PROJECT_HEAVY_NOTE = "This course is primarily independent project work."


@dataclass(frozen=True)
class ScoringContext:
    """Everything the signals may read besides the course itself."""

    role_skills: tuple[str, ...]
    skill_gaps: frozenset[str]
    preferences: tuple[str, ...]
    curated_courses: frozenset[str]
    project_averse: bool


def gap_skills(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    return tuple(s for s in course.skills if s in ctx.skill_gaps)


def role_skills(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    """Role skills the course covers that aren't gaps (gaps score on their own)."""
    return tuple(s for s in course.skills if s in ctx.role_skills and s not in ctx.skill_gaps)


def preference_matches(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    haystack = f"{course.title}\n{course.section}\n{course.description}".lower()
    return tuple(p for p in ctx.preferences if p.strip() and p.strip().lower() in haystack)


def _skill_gap(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = gap_skills(course, ctx)
    if not matched:
        return None
    return ScoreItem("skill_gap", tuning.W_GAP_SKILL * len(matched), "closes skill gaps: " + ", ".join(matched))


def _role_skill(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = role_skills(course, ctx)
    if not matched:
        return None
    return ScoreItem("role_skill", tuning.W_ROLE_SKILL * len(matched), "covers role-relevant skills: " + ", ".join(matched))


def _preference(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = preference_matches(course, ctx)
    if not matched:
        return None
    return ScoreItem("preference", tuning.W_PREFERENCE * len(matched), "matches your stated interests: " + ", ".join(matched))


def _curated(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if course.code not in ctx.curated_courses:
        return None
    return ScoreItem("curated_role_course", tuning.W_CURATED_ROLE, "on the curated shortlist for this role")


def _project_heavy(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if not (ctx.project_averse and course.workload_shape == "project_heavy"):
        return None
    return ScoreItem("project_heavy", tuning.PROJECT_HEAVY_PENALTY, PROJECT_HEAVY_NOTE)


SIGNALS: tuple[Callable[[Course, ScoringContext], ScoreItem | None], ...] = (
    _skill_gap,
    _role_skill,
    _preference,
    _curated,
    _project_heavy,
)
