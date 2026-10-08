"""
STAGE 2 (second half) — hard eligibility rules. Pure code, no LLM, no I/O.

Division of labour: this file decides WHO IS ALLOWED into the candidate
pool (exclude completed courses, preclusion conflicts, non-recommendable
courses, data still under review) and computes hard facts (completed
units, skill gaps, prerequisite/corequisite cautions). WHICH courses end
up recommended is STAGE 4/5's job (requirement_slots.py, scoring.py,
selection.py), working strictly from the pool this module produces.

Everything here is deterministic and has no database or LLM dependency —
straightforward to unit-test in isolation.
"""

from __future__ import annotations

import re

from app.domains.specialist.course_recommendation.models import (
    CandidatePool,
    Course,
    ExcludedCourse,
)

_COURSE_CODE = re.compile(r"^[A-Z]{2,4}\d{4}[A-Z]?$")


def normalize_codes(raw_codes: list[str]) -> tuple[list[str], list[str]]:
    """Uppercase, strip, dedup (order kept). Returns (codes, non_codes):
    entries that cannot be a course code (e.g. a reported course title like
    "Machine Learning") go into non_codes so they can be
    reported as unrecognized instead of silently vanishing."""
    seen: set[str] = set()
    codes: list[str] = []
    non_codes: list[str] = []
    for raw in raw_codes:
        entry = raw.strip()
        if not entry:
            continue
        code = entry.upper()
        if _COURSE_CODE.fullmatch(code):
            if code not in seen:
                seen.add(code)
                codes.append(code)
        elif entry not in non_codes:
            non_codes.append(entry)
    return codes, non_codes


def _codes_in(text: str, codes: list[str]) -> tuple[str, ...]:
    """Which of `codes` appear (as whole words) in `text`."""
    return tuple(
        code
        for code in codes
        if re.search(rf"\b{re.escape(code)}\b", text, flags=re.IGNORECASE)
    )


def _catalogue_codes_in(text: str, catalogue_codes: set[str]) -> tuple[str, ...]:
    """Which known catalogue course codes are named anywhere in free text —
    used to tell "this prerequisite names a real course" apart from
    "this prerequisite is prose with no checkable course code at all"
    (e.g. "instructor's consent required")."""
    return tuple(
        code
        for code in catalogue_codes
        if re.search(rf"\b{re.escape(code)}\b", text, flags=re.IGNORECASE)
    )


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
         courses flagged needs_review, minus courses whose preclusion_codes
         name a completed course.
      4. Prerequisite SOFT caution (does not exclude): a still-eligible
         course whose prerequisite text names a real catalogue course code
         that is not among the student's completed courses. Free-text
         prerequisites with no checkable course code (e.g. "instructor's
         consent") never trigger this — there is nothing to verify.
    No ranking happens here — the pool goes to STAGE 4 as-is.
    """
    completed, non_codes = normalize_codes(completed_codes)
    by_code = {c.code: c for c in courses}
    catalogue_codes = set(by_code)

    completed_recognized = [c for c in completed if c in by_code]
    # Unknown codes and free-text titles both end up here — reported, never
    # silently dropped.
    completed_unrecognized = [c for c in completed if c not in by_code] + non_codes
    completed_units = sum(by_code[c].units for c in completed_recognized)

    covered_skills = {s for c in completed_recognized for s in by_code[c].skills}
    skill_gaps = tuple(s for s in role_skills if s not in covered_skills)

    eligible: list[Course] = []
    excluded_courses: list[ExcludedCourse] = []
    preclusion_exclusions: list[tuple[str, str]] = []
    prerequisite_cautions: list[str] = []
    for course in courses:
        if course.code in completed_recognized:
            excluded_courses.append(
                {"course_code": course.code, "reason": "already_completed"}
            )
            continue
        if not course.can_recommend:
            excluded_courses.append(
                {"course_code": course.code, "reason": "not_recommendable"}
            )
            continue
        if course.data_quality == "needs_review":
            excluded_courses.append(
                {"course_code": course.code, "reason": "needs_review"}
            )
            continue
        precluded_by = _codes_in(course.preclusion_text, completed_recognized)
        if precluded_by:
            related_course_code = precluded_by[0]
            preclusion_exclusions.append((course.code, related_course_code))
            excluded_courses.append(
                {
                    "course_code": course.code,
                    "reason": "precluded_by_completed_course",
                    "related_course_code": related_course_code,
                }
            )
            continue
        named_prereq_codes = _catalogue_codes_in(course.prerequisite_text, catalogue_codes)
        if named_prereq_codes and not _codes_in(course.prerequisite_text, completed_recognized):
            prerequisite_cautions.append(course.code)
        eligible.append(course)

    notes: list[str] = []
    if completed_unrecognized:
        notes.append(
            "Not found in the course catalogue and ignored: "
            + ", ".join(completed_unrecognized)
        )
    if preclusion_exclusions:
        notes.append(
            "Excluded due to preclusion against a completed course: "
            + ", ".join(
                f"{cand} (precluded by {done})" for cand, done in preclusion_exclusions
            )
        )

    return CandidatePool(
        eligible=tuple(eligible),
        skill_gaps=skill_gaps,
        completed_recognized=tuple(completed_recognized),
        completed_unrecognized=tuple(completed_unrecognized),
        completed_units=completed_units,
        notes=tuple(notes),
        excluded_courses=tuple(excluded_courses),
        prerequisite_cautions=tuple(prerequisite_cautions),
    )
