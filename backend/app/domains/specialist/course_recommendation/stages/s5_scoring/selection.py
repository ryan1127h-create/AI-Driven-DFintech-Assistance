"""
S5 (second half) — deterministic selection within one requirement slot.

Takes a slot's scored candidates (scorer.py) and returns its
`display_count` picks in best-first order: the first
`required_pick_count` are the recommendation, the rest browsable
alternatives (workflow.py and the mode assemble the groups from that
split). Each pick's reason is built from its score breakdown, so every
reason is backed by a signal that actually fired.

Pure function, no I/O, no LLM.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import (
    Pick,
    RequirementSlot,
    ScoredCourse,
)
from app.domains.specialist.course_recommendation.policy import tuning


def best_pair(scored: list[ScoredCourse]) -> tuple[ScoredCourse, ScoredCourse] | None:
    """For a 2-pick slot: among the top-scored candidates, prefer the pair
    that jointly covers the most distinct skills over the pair that is
    merely individually highest-scored — avoids recommending two courses
    that teach the same thing when the slot needs two picks. None if
    fewer than 2 candidates are available."""
    window = scored[:tuning.PAIR_CANDIDATE_WINDOW]
    if len(window) < 2:
        return None

    best: tuple[ScoredCourse, ScoredCourse] | None = None
    best_key: tuple[int, float] | None = None
    for i in range(len(window)):
        for j in range(i + 1, len(window)):
            first, second = window[i], window[j]
            union_size = len(set(first.course.skills) | set(second.course.skills))
            key = (union_size, first.score + second.score)
            if best_key is None or key > best_key:
                best_key = key
                best = (first, second)
    return best


def rank_for_slot(
    scored: list[ScoredCourse], required_pick_count: int, display_count: int
) -> list[ScoredCourse]:
    """The slot's display order: the first `required_pick_count` entries
    are the actual recommendation (using best_pair's complementarity check
    when 2 are needed), the remaining entries up to `display_count` are
    the best-scoring leftovers."""
    if not scored:
        return []

    if required_pick_count >= 2:
        pair = best_pair(scored)
        primary = list(pair) if pair is not None else scored[:required_pick_count]
    else:
        primary = scored[:required_pick_count]

    primary_codes = {sc.course.code for sc in primary}
    filler = [sc for sc in scored if sc.course.code not in primary_codes]
    return (primary + filler)[:display_count]


def reason_for(scored: ScoredCourse, slot: RequirementSlot) -> str:
    """One sentence of evidence from the score breakdown, falling back to
    the requirement the course counts toward when no signal fired."""
    evidence = [item.evidence for item in scored.breakdown] or [f"counts toward {slot.label}"]
    text = "; ".join(evidence)
    return text[0].upper() + text[1:] + "."


def select_for_slot(slot: RequirementSlot, scored: list[ScoredCourse]) -> list[Pick]:
    return [
        Pick(scored=sc, reason=reason_for(sc, slot))
        for sc in rank_for_slot(scored, slot.required_pick_count, slot.display_count)
    ]
