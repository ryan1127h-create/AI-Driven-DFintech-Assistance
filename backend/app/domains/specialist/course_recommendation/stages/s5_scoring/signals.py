"""
S5 scoring signals — one function per signal, all collected in SIGNALS.

Each signal looks at one course in a ScoringContext and returns the
ScoreItem it contributes, or None when it doesn't apply. A signal only
fires when its input was actually supplied (no role -> no role signals;
no workload preference -> no project-heavy penalty), so a missing input
never skews a ranking. Weights come from policy/tuning.py.

Role fit rests on the course's own role tags. Course skills are derived
from those tags and so are coarse — "programming" is on ~90% of courses —
which is why the skill signals only count distinctive skills (carried by
at most tuning.DISTINCTIVE_SKILL_MAX_SHARE of the catalogue): a skill
nearly every course has can't tell one course from another.

To add a signal: write one function here, append it to SIGNALS, and give
it a weight in policy/tuning.py. scorer.py needs no change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.domains.specialist.course_recommendation.models import Course, ScoreItem
from app.domains.specialist.course_recommendation.policy import tuning

PROJECT_HEAVY_NOTE = "This course is primarily independent project work."

# Display text for the knowledge base's skill vocabulary (contracts.SkillId).
SKILL_LABELS = {
    "ai_ml": "AI and machine learning",
    "data_analytics": "data analytics",
    "data_engineering": "data engineering",
    "finance": "finance",
    "payments_systems": "payment systems",
    "product": "product management",
    "programming": "programming",
    "regulation": "regulation",
    "risk_modeling": "risk modelling",
    "security": "security",
}


@dataclass(frozen=True)
class ScoringContext:
    """Everything the signals may read besides the course itself."""

    target_role_tag: str | None
    role_skills: tuple[str, ...]
    skill_gaps: frozenset[str]
    # skill -> share of the recommendable catalogue that carries it.
    skill_share: dict[str, float]
    preferences: tuple[str, ...]
    project_averse: bool
    # What the student asked for this turn (all optional).
    requested_codes: frozenset[str] = frozenset()
    preferred_skills: tuple[str, ...] = ()
    interest_verticals: frozenset[str] = frozenset()
    prefers_lecture: bool = False


def skill_shares(courses: list[Course]) -> dict[str, float]:
    """skill -> share of the recommendable courses that carry it."""
    recommendable = [c for c in courses if c.can_recommend]
    if not recommendable:
        return {}
    counts: dict[str, int] = {}
    for course in recommendable:
        for skill in set(course.skills):
            counts[skill] = counts.get(skill, 0) + 1
    return {skill: count / len(recommendable) for skill, count in counts.items()}


def distinctive(skills: tuple[str, ...], skill_share: dict[str, float]) -> tuple[str, ...]:
    """The skills rare enough in the catalogue to tell courses apart."""
    return tuple(s for s in skills if skill_share.get(s, 1.0) <= tuning.DISTINCTIVE_SKILL_MAX_SHARE)


def gap_skills(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    return tuple(s for s in course.skills if s in ctx.skill_gaps)


def role_skills(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    """Role skills the course covers that aren't gaps (gaps score on their own)."""
    return tuple(s for s in course.skills if s in ctx.role_skills and s not in ctx.skill_gaps)


def preference_matches(course: Course, ctx: ScoringContext) -> tuple[str, ...]:
    haystack = f"{course.title}\n{course.section}\n{course.description}".lower()
    return tuple(p for p in ctx.preferences if p.strip() and p.strip().lower() in haystack)


def is_tagged_for_target(course: Course, ctx: ScoringContext) -> bool:
    return ctx.target_role_tag is not None and any(tag == ctx.target_role_tag for tag, _ in course.role_tags)


def _role_tag(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if not is_tagged_for_target(course, ctx):
        return None
    return ScoreItem("role_tag", tuning.W_ROLE_TAG_MATCH, "tagged for the target role")


def _skill_gap(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = distinctive(gap_skills(course, ctx), ctx.skill_share)
    if not matched:
        return None
    return ScoreItem("skill_gap", tuning.W_GAP_SKILL * len(matched), "closes skill gaps: " + ", ".join(matched))


def _role_skill(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = distinctive(role_skills(course, ctx), ctx.skill_share)
    if not matched:
        return None
    return ScoreItem("role_skill", tuning.W_ROLE_SKILL * len(matched), "covers role-relevant skills: " + ", ".join(matched))


def _preference(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    matched = preference_matches(course, ctx)
    if not matched:
        return None
    return ScoreItem("preference", tuning.W_PREFERENCE * len(matched), "matches your interest in " + ", ".join(matched))


def _requested(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if course.code not in ctx.requested_codes:
        return None
    return ScoreItem("requested", tuning.W_REQUESTED, "you asked for this course")


def _preferred_skill(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    # Only distinctive skills: a common derived skill can't show that a
    # course actually builds what the student asked for.
    matched = distinctive(tuple(s for s in course.skills if s in ctx.preferred_skills), ctx.skill_share)
    if not matched:
        return None
    labels = ", ".join(SKILL_LABELS.get(s, s) for s in matched)
    return ScoreItem("preferred_skill", tuning.W_PREFERENCE * len(matched), f"builds {labels}, which you asked for")


def _vertical_interest(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if not ctx.interest_verticals.intersection(course.vertical):
        return None
    return ScoreItem("vertical_interest", tuning.W_VERTICAL_INTEREST, "in a Vertical you're interested in")


def _workload_fit(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if not (ctx.prefers_lecture and course.workload_shape == "lecture_heavy"):
        return None
    return ScoreItem("workload_fit", tuning.W_WORKLOAD_FIT, "lecture-based, as you prefer")


def _project_heavy(course: Course, ctx: ScoringContext) -> ScoreItem | None:
    if not (ctx.project_averse and course.workload_shape == "project_heavy"):
        return None
    return ScoreItem("project_heavy", tuning.PROJECT_HEAVY_PENALTY, PROJECT_HEAVY_NOTE)


SIGNALS: tuple[Callable[[Course, ScoringContext], ScoreItem | None], ...] = (
    _role_tag,
    _skill_gap,
    _role_skill,
    _requested,
    _preferred_skill,
    _preference,
    _vertical_interest,
    _workload_fit,
    _project_heavy,
)

# The signals that answer what the student asked for this turn — their
# evidence is worded for the student and shown as a reason.
REQUEST_SIGNALS = frozenset({"requested", "preferred_skill", "preference", "vertical_interest", "workload_fit"})
