"""
Hard eligibility rules — pure code, no LLM, no I/O.

Division of labour: this file decides WHO IS ALLOWED into the candidate
pool (exclude completed courses, preclusion conflicts, non-recommendable
courses) and computes hard facts (units, skill gaps). WHICH courses to
actually recommend is the LLM's choice (agents/recommendation_agent.py),
picked strictly from this pool. score_candidates() below is only the
fallback ranking used when the LLM is unavailable.

Everything here is deterministic and has no database or LLM dependency —
straightforward to unit-test in isolation, though no such test file exists
in this repo yet (see backend/tests/ for what is currently covered).
"""

from __future__ import annotations

import re

from app.modules.course_recommendation.models import (
    CandidatePool,
    Course,
    ScoredCourse,
)

# Fallback-ranking weights (only used when the LLM selector fails):
# closing a skill gap counts most, then covering another role skill,
# then matching a user preference keyword.
W_GAP_SKILL = 2.0
W_ROLE_SKILL = 1.0
W_PREFERENCE = 1.5

# Fallback priority bands over the score above.
PRIORITY_HIGH_MIN = 4.0
PRIORITY_MEDIUM_MIN = 2.0

MAX_RECOMMENDATIONS = 8

_COURSE_CODE = re.compile(r"^[A-Z]{2,4}\d{4}[A-Z]?$")


def normalize_codes(raw_codes: list[str]) -> tuple[list[str], list[str]]:
    """Uppercase, strip, dedup (order kept). Returns (codes, non_codes):
    entries that cannot be a course code (e.g. a course *title* from the
    profile, like "Machine Learning") go into non_codes so they can be
    reported as unrecognized instead of silently vanishing."""
    seen: set[str] = set()
    codes: list[str] = []
    non_codes: list[str] = []
    for raw in raw_codes:
        entry = raw.strip()
        if not entry:
            continue
        code = entry.upper()
        if _COURSE_CODE.match(code):
            if code not in seen:
                seen.add(code)
                codes.append(code)
        elif entry not in non_codes:
            non_codes.append(entry)
    return codes, non_codes


def _codes_in(text: str, codes: list[str]) -> tuple[str, ...]:
    """Which of `codes` appear (as whole words) in `text`."""
    return tuple(c for c in codes if re.search(rf"\b{re.escape(c)}\b", text))


def build_candidate_pool(
    courses: list[Course],
    completed_codes: list[str],
    role_skills: list[str],
) -> CandidatePool:
    """
    Applies the HARD rules only:
      1. Recognise completed courses against the catalogue; count their units.
      2. Skill gaps = role skills not covered by any completed course.
      3. Eligible candidates = can_recommend courses, minus completed, minus
         courses whose Preclusion text names a completed course.
    No ranking happens here — the pool goes to the LLM as-is.
    """
    completed, non_codes = normalize_codes(completed_codes)
    by_code = {c.code: c for c in courses}

    completed_recognized = [c for c in completed if c in by_code]
    # Unknown codes and free-text titles (e.g. prior-degree courses from the
    # profile) both end up here — reported, never silently dropped.
    completed_unrecognized = [c for c in completed if c not in by_code] + non_codes
    completed_units = sum(by_code[c].units for c in completed_recognized)

    covered_skills = {s for c in completed_recognized for s in by_code[c].skills}
    skill_gaps = tuple(s for s in role_skills if s not in covered_skills)

    eligible: list[Course] = []
    excluded: list[tuple[str, str]] = []
    for course in courses:
        if not course.can_recommend or course.code in completed_recognized:
            continue
        precluded_by = _codes_in(course.preclusion_text, completed_recognized)
        if precluded_by:
            excluded.append((course.code, precluded_by[0]))
            continue
        eligible.append(course)

    notes: list[str] = []
    if completed_unrecognized:
        notes.append(
            "Not found in the course catalogue and ignored: "
            + ", ".join(completed_unrecognized)
        )
    if excluded:
        notes.append(
            "Excluded due to preclusion against a completed course: "
            + ", ".join(f"{cand} (precluded by {done})" for cand, done in excluded)
        )

    return CandidatePool(
        eligible=tuple(eligible),
        skill_gaps=skill_gaps,
        completed_recognized=tuple(completed_recognized),
        completed_unrecognized=tuple(completed_unrecognized),
        completed_units=completed_units,
        excluded_by_preclusion=tuple(excluded),
        notes=tuple(notes),
    )


def matched_skills_of(course: Course, role_skills: list[str]) -> list[str]:
    """The course skills that matter for this role — computed by code so the
    API always shows verified tags, whoever picked the course."""
    return [s for s in course.skills if s in role_skills]


def _preference_matches(course: Course, preferences: list[str]) -> tuple[str, ...]:
    """Case-insensitive substring match of each preference keyword against
    the course's title, section, and description."""
    haystack = f"{course.title}\n{course.section}\n{course.description}".lower()
    return tuple(p for p in preferences if p.strip() and p.strip().lower() in haystack)


def score_candidates(
    pool: CandidatePool,
    role_skills: list[str],
    preferences: list[str],
    completed_recognized: tuple[str, ...],
) -> list[ScoredCourse]:
    """
    FALLBACK ranking, used only when the LLM selector fails: weighted count
    of gap skills / other role skills / preference keyword hits. With no
    signal at all, falls back to the not-yet-completed Core Courses.
    Returns at most MAX_RECOMMENDATIONS, best first.
    """
    skill_gaps = set(pool.skill_gaps)
    has_signal = bool(role_skills or any(p.strip() for p in preferences))

    scored: list[ScoredCourse] = []
    for course in pool.eligible:
        matched_gap = tuple(s for s in course.skills if s in skill_gaps)
        # Gap skills excluded here so each skill scores exactly once.
        matched_role = tuple(
            s for s in course.skills if s in role_skills and s not in skill_gaps
        )
        matched_prefs = _preference_matches(course, preferences)
        prereq_met = _codes_in(course.prerequisite_text, list(completed_recognized))

        score = (
            W_GAP_SKILL * len(matched_gap)
            + W_ROLE_SKILL * len(matched_role)
            + W_PREFERENCE * len(matched_prefs)
        )

        if has_signal:
            if score <= 0:
                continue
        elif not course.is_core:
            continue  # no signal at all: recommend remaining Core Courses

        scored.append(ScoredCourse(
            course=course,
            score=score,
            matched_gap_skills=matched_gap,
            matched_role_skills=matched_role,
            matched_preferences=matched_prefs,
            prerequisite_met_by=prereq_met,
        ))

    scored.sort(key=lambda s: (-s.score, s.course.code))
    return scored[:MAX_RECOMMENDATIONS]


def priority_of(score: float) -> str:
    """Fallback priority band for a fallback score."""
    if score >= PRIORITY_HIGH_MIN:
        return "high"
    if score >= PRIORITY_MEDIUM_MIN:
        return "medium"
    return "low"
