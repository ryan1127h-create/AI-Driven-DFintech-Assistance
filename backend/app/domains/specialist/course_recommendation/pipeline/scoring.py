"""
STAGE 5 (first half) — per-slot multi-signal scoring.

Unlike the old flat design, a slot's candidates are already scoped to one
requirement category (STAGE 4), so scoring never needs a "which category
is most urgent" weight — it only has to rank a handful of courses that
all count toward the SAME requirement. Every term below only activates
when its input signal was actually supplied (see SignalAvailability in
the confirmed design): no role -> no role-fit term; no workload
preference -> no workload term. This is also the FALLBACK ranking used
whenever STAGE 5's LLM proposal (selection.py) is unavailable or fails
validation after its retries.

Pure function, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, ScoredCourse

W_GAP_SKILL = 2.0
W_ROLE_SKILL = 1.0
W_PREFERENCE = 1.5
W_CURATED_ROLE = 1.0
PROJECT_HEAVY_PENALTY = -1.0

# How many top-scored candidates are considered when picking the best PAIR
# for a 2-pick slot — the eligible pool per slot is always small (a
# handful of courses), so this stays cheap.
PAIR_CANDIDATE_WINDOW = 4


def _preference_matches(course: Course, preferences: list[str]) -> tuple[str, ...]:
    haystack = f"{course.title}\n{course.section}\n{course.description}".lower()
    return tuple(p for p in preferences if p.strip() and p.strip().lower() in haystack)


def matched_skills_of(course: Course, role_skills: list[str]) -> list[str]:
    """The course skills that matter for this role — computed by code so the
    API always shows verified tags, whoever picked the course."""
    return [s for s in course.skills if s in role_skills]


def score_slot_candidates(
    candidates: tuple[Course, ...],
    role_skills: list[str],
    skill_gaps: tuple[str, ...],
    preferences: list[str],
    curated_role_courses: list[str],
    project_averse: bool,
) -> list[ScoredCourse]:
    """Scores and sorts (best first) every candidate in one requirement
    slot. Never raises on empty input — the caller (service.py) already
    knows to skip a slot with zero candidates before reaching here."""
    skill_gap_set = set(skill_gaps)
    curated_set = set(curated_role_courses)

    scored: list[ScoredCourse] = []
    for course in candidates:
        matched_gap = tuple(s for s in course.skills if s in skill_gap_set)
        matched_role = tuple(
            s for s in course.skills if s in role_skills and s not in skill_gap_set
        )
        matched_prefs = _preference_matches(course, preferences)
        curated_match = course.code in curated_set

        score = (
            W_GAP_SKILL * len(matched_gap)
            + W_ROLE_SKILL * len(matched_role)
            + W_PREFERENCE * len(matched_prefs)
            + (W_CURATED_ROLE if curated_match else 0.0)
        )

        workload_note: str | None = None
        if project_averse and course.workload_shape == "project_heavy":
            score += PROJECT_HEAVY_PENALTY
            workload_note = "This course is primarily independent project work."

        scored.append(
            ScoredCourse(
                course=course,
                score=score,
                matched_gap_skills=matched_gap,
                matched_role_skills=matched_role,
                matched_preferences=matched_prefs,
                curated_match=curated_match,
                workload_note=workload_note,
            )
        )

    scored.sort(key=lambda s: (-s.score, s.course.code))
    return scored


def best_pair(scored: list[ScoredCourse]) -> tuple[ScoredCourse, ScoredCourse] | None:
    """For a 2-pick slot: among the top-scored candidates, prefer the pair
    that jointly covers the most distinct skills over the pair that is
    merely individually highest-scored — avoids recommending two courses
    that teach the same thing when the slot needs two picks. None if
    fewer than 2 candidates are available."""
    window = scored[:PAIR_CANDIDATE_WINDOW]
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
    """Deterministic fallback ordering for a whole slot: the first
    `required_pick_count` entries are the actual recommendation (using
    best_pair's complementarity check when 2 are needed), the remaining
    entries up to `display_count` are the best-scoring leftovers, shown as
    browsable alternatives. Used by selection.fallback_for_slot(); the LLM
    path picks its own `display_count` from the full scored list instead
    of this pre-narrowed order."""
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
