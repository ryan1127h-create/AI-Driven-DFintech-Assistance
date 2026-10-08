"""
S5 (first half) — per-slot scoring.

A slot's candidates are already scoped to one requirement category (S4),
so scoring only has to rank a handful of courses that all count toward
the SAME requirement. Every signal in signals.SIGNALS contributes one
ScoreItem; a course's score is the sum of its items, and the items are
kept as its auditable breakdown.

Pure function, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, ScoredCourse
from app.domains.specialist.course_recommendation.stages.s5_scoring import signals


def score_slot_candidates(candidates: tuple[Course, ...], ctx: signals.ScoringContext) -> list[ScoredCourse]:
    """Scores and sorts (best first, ties by course code) every candidate
    in one requirement slot. Never raises on empty input — the caller
    (workflow.py) already skips a slot with zero candidates."""
    scored: list[ScoredCourse] = []
    for course in candidates:
        breakdown = tuple(item for signal in signals.SIGNALS if (item := signal(course, ctx)) is not None)
        scored.append(
            ScoredCourse(
                course=course,
                score=sum(item.delta for item in breakdown),
                matched_gap_skills=signals.gap_skills(course, ctx),
                matched_role_skills=signals.role_skills(course, ctx),
                matched_preferences=signals.preference_matches(course, ctx),
                role_tag_match=signals.is_tagged_for_target(course, ctx),
                workload_note=next(
                    (item.evidence for item in breakdown if item.signal == "project_heavy"), None
                ),
                breakdown=breakdown,
            )
        )

    scored.sort(key=lambda s: (-s.score, s.course.code))
    return scored
