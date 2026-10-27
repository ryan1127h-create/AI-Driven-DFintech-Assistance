"""
S4 — scores each role family against the student's graded skills (S3).
Pure code, no LLM, no I/O.

A role's fit is the mean evidence points of its required skills (unknown
counts as 0), plus policy.tuning.FUNCTION_AFFINITY_BONUS when the
student has worked in the role's line of work (half of it for an
internship only), capped at 1. A fit resting on mostly-unknown skills is
flagged low-confidence: it says more about the profile's gaps than about
the student.

Each role also carries the programme's course support for it: the courses
tagged for it, and which of those the student has taken or is taking.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domains.specialist.career_planning.models import (
    CourseLink,
    CourseSupport,
    RoleDefinition,
    RoleFit,
    SkillAssessment,
    StudentEvidence,
)
from app.domains.specialist.career_planning.policy import tuning


def course_support(role: RoleDefinition, evidence: StudentEvidence, links: tuple[CourseLink, ...]) -> CourseSupport:
    codes = tuple(sorted(link.code for link in links if role.tag in link.tags))
    return CourseSupport(
        course_codes=codes,
        taken=tuple(c for c in evidence.completed_courses if c in codes),
        taking=tuple(c for c in evidence.current_courses if c in codes),
    )


def _experience_bonus(role: RoleDefinition, evidence: StudentEvidence) -> tuple[float, tuple[str, ...]]:
    related = [f for f in evidence.functions if role.tag in tuning.FUNCTION_ROLE_AFFINITY.get(f.key, ())]
    if not related:
        return 0.0, ()
    keys = tuple(dict.fromkeys(f.key for f in related))
    full = any(not f.internship for f in related)
    return tuning.FUNCTION_AFFINITY_BONUS * (1.0 if full else 0.5), keys


def fit_role(
    role: RoleDefinition,
    assessments: Mapping[str, SkillAssessment],
    evidence: StudentEvidence,
    links: tuple[CourseLink, ...],
    preferred: frozenset[str] = frozenset(),
) -> RoleFit:
    graded = [assessments[skill] for skill in role.required_skills]
    by_status = {
        status: tuple(a.skill for a in graded if a.status == status)
        for status in ("met", "partial", "missing", "unknown")
    }
    bonus, experience = _experience_bonus(role, evidence)
    cap = 1.0 if len(by_status["met"]) == len(graded) else tuning.FIT_CAP_WITH_GAPS
    fit = min(cap, sum(a.points for a in graded) / len(graded) + bonus)
    unknown_share = len(by_status["unknown"]) / len(graded)
    return RoleFit(
        role=role,
        fit=round(fit, 3),
        unknown_share=round(unknown_share, 3),
        low_confidence=unknown_share > tuning.LOW_CONFIDENCE_UNKNOWN_SHARE,
        met_skills=by_status["met"],
        partial_skills=by_status["partial"],
        missing_skills=by_status["missing"],
        unknown_skills=by_status["unknown"],
        experience=experience,
        preferred=role.tag in preferred,
        support=course_support(role, evidence, links),
    )


def rank_roles(
    roles: tuple[RoleDefinition, ...],
    assessments: Mapping[str, SkillAssessment],
    evidence: StudentEvidence,
    links: tuple[CourseLink, ...],
    preferred: frozenset[str] = frozenset(),
) -> list[RoleFit]:
    """Every role, best fit first; ties go to the better-evidenced role,
    then the one the student lists, then by tag (stable output)."""
    fits = [fit_role(role, assessments, evidence, links, preferred) for role in roles]
    return sorted(fits, key=lambda f: (-f.fit, f.unknown_share, not f.preferred, f.role.tag))
