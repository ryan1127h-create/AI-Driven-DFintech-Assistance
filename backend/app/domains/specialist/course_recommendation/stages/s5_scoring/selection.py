"""
S5 (second half) — deterministic selection within one requirement slot.

Takes a slot's scored candidates (scorer.py) and returns its
`display_count` picks in best-first order: the first
`required_pick_count` are the recommendation, the rest browsable
alternatives (workflow.py and the mode assemble the groups from that
split). Each pick carries its synopsis and evidence (evidence.py); its
plain-text reason, used when the reply falls back to a template, is
built from that evidence.

Pure function, no I/O, no LLM.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import (
    Pick,
    RequirementSlot,
    ScoredCourse,
)
from app.domains.specialist.course_recommendation.policy import tuning
from app.domains.specialist.course_recommendation.stages.s5_scoring.evidence import (
    EvidenceContext,
    evidence_for,
    synopsis,
)


def best_pair(scored: list[ScoredCourse]) -> tuple[ScoredCourse, ScoredCourse] | None:
    """For a 2-pick slot: the highest-scoring pair among the top-scored
    candidates, and among equally scored pairs the one spanning the most
    distinct role tags — so two equally good courses aimed at the same
    roles don't crowd out a complementary one. Fit comes first: a
    complementary course never displaces a better-scoring one. (Derived
    skills aren't used to judge complementarity: they're too coarse — most
    courses share "programming" and "data analytics".) None if fewer than
    2 candidates are available."""
    window = scored[:tuning.PAIR_CANDIDATE_WINDOW]
    if len(window) < 2:
        return None

    best: tuple[ScoredCourse, ScoredCourse] | None = None
    best_key: tuple[float, int] | None = None
    for i in range(len(window)):
        for j in range(i + 1, len(window)):
            first, second = window[i], window[j]
            role_union = len(set(first.course.role_tags) | set(second.course.role_tags))
            key = (first.score + second.score, role_union)
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


def reason_from(evidence: tuple[str, ...], slot: RequirementSlot) -> str:
    """The evidence as one sentence, falling back to the requirement the
    course counts toward when there is none."""
    text = "; ".join(evidence) or f"counts toward {slot.label}"
    return text[0].upper() + text[1:] + "."


def select_for_slot(slot: RequirementSlot, scored: list[ScoredCourse], ctx: EvidenceContext) -> list[Pick]:
    picks = []
    for sc in rank_for_slot(scored, slot.required_pick_count, slot.display_count):
        evidence = evidence_for(sc, slot, ctx)
        picks.append(Pick(
            scored=sc, reason=reason_from(evidence, slot),
            synopsis=synopsis(sc.course.description), evidence=evidence,
        ))
    return picks
