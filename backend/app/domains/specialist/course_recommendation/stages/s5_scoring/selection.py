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
from app.domains.specialist.course_recommendation.stages.s5_scoring.signals import REQUEST_SIGNALS


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


def _pick(sc: ScoredCourse, slot: RequirementSlot | None, ctx: EvidenceContext, fallback_label: str) -> Pick:
    """A pick with its synopsis, evidence, and the evidence as a one-sentence
    reason (falling back to the requirement when there's no evidence)."""
    evidence = evidence_for(sc, slot, ctx)
    text = "; ".join(evidence) or f"counts toward {fallback_label}"
    return Pick(
        scored=sc, reason=text[0].upper() + text[1:] + ".",
        synopsis=synopsis(sc.course.description), evidence=evidence, slot=slot,
    )


def select_top(
    scored: list[ScoredCourse],
    slot_by_code: dict[str, RequirementSlot],
    count: int,
    ctx: EvidenceContext,
) -> tuple[list[Pick], bool]:
    """The ad_hoc selection: the best `count` courses across every slot.
    Only courses matching something the student asked for are listed,
    ranked by how well they match it first and their overall score second
    — a course that fits the student's role but barely the request mustn't
    lead. When none matches, the best general fits are returned instead.
    Returns (picks, whether they match the request)."""
    def request_score(sc: ScoredCourse) -> float:
        return sum(item.delta for item in sc.breakdown if item.signal in REQUEST_SIGNALS)

    matching = [sc for sc in scored if any(item.signal in REQUEST_SIGNALS for item in sc.breakdown)]
    matching.sort(key=lambda sc: (-request_score(sc), -sc.score, sc.course.code))
    chosen = (matching or scored)[:count]
    picks = [_pick(sc, slot_by_code.get(sc.course.code), ctx, "your degree") for sc in chosen]
    return picks, bool(matching)


def select_for_slot(slot: RequirementSlot, scored: list[ScoredCourse], ctx: EvidenceContext) -> list[Pick]:
    return [
        _pick(sc, slot, ctx, slot.label)
        for sc in rank_for_slot(scored, slot.required_pick_count, slot.display_count)
    ]
