"""
S5 — what a recommendation is explained with. For each picked course:

  - a synopsis: the opening sentences of its description, the only
    source the reply may draw on for what the course teaches;
  - evidence: short, checkable facts for why it fits this student — the
    requirement it counts toward, its direct role tags, skill gaps it
    closes, how it's taught, when it runs, a prerequisite already met.

Skills are only named when they are distinctive: course skills are
derived from role tags and very common ones ("programming" is on ~90% of
courses) explain nothing, so a skill carried by more than
tuning.DISTINCTIVE_SKILL_MAX_SHARE of the catalogue is left out. The role
relation uses the course's own role tags, never those derived skills.

Pure functions, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domains.specialist.course_recommendation.models import (
    Course,
    RequirementSlot,
    ScoredCourse,
)
from app.domains.specialist.course_recommendation.policy import tuning

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

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_MAX_OTHER_ROLES = 3


@dataclass(frozen=True)
class EvidenceContext:
    # (tag, display name) of the student's target role, if one resolved.
    target_role: tuple[str, str] | None
    # skill -> share of the recommendable catalogue that carries it.
    skill_share: dict[str, float]
    prerequisite_cautions: frozenset[str]


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


def synopsis(description: str) -> str:
    """The description's opening sentences, up to tuning.SYNOPSIS_MAX_CHARS;
    a first sentence longer than that is cut at a word boundary."""
    text = " ".join(description.split())
    if not text:
        return ""
    result = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{result} {sentence}".strip()
        if len(candidate) > tuning.SYNOPSIS_MAX_CHARS:
            break
        result = candidate
    if result:
        return result
    cut = text[:tuning.SYNOPSIS_MAX_CHARS].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _skills_text(skills: list[str]) -> str:
    return ", ".join(SKILL_LABELS.get(s, s) for s in skills)


def _requirement(slot: RequirementSlot) -> str:
    if slot.slot_type == "core_mandatory":
        return (
            f"one of the {len(slot.eligible_candidates)} mandatory core courses you still need"
            if len(slot.eligible_candidates) > 1 else "the last mandatory core course you still need"
        )
    if slot.slot_type == "core_choice":
        return "counts toward the core course choice (3 of the 11 FT50xx courses)"
    if slot.slot_type == "capstone":
        return "the Capstone project"
    if slot.required_pick_count == 0:
        return f"an optional elective in {slot.label}"
    return f"counts toward your remaining electives ({slot.label})"


def _role_relation(course: Course, slot: RequirementSlot, target_role: tuple[str, str] | None) -> str | None:
    if not course.role_tags:
        return None
    tags = dict(course.role_tags)
    if target_role and target_role[0] in tags:
        others = [name for tag, name in course.role_tags if tag != target_role[0]][:_MAX_OTHER_ROLES]
        text = f"tagged for your target role, {target_role[1]}"
        return f"{text}, and also for {', '.join(others)}" if others else text
    if slot.slot_type == "core_mandatory":
        # Required whatever the student's direction, so a mismatch with the
        # target role is no reason for or against it.
        return None
    names = ", ".join(name for _, name in course.role_tags[:_MAX_OTHER_ROLES])
    if target_role:
        return f"aimed at {names} roles rather than {target_role[1]}"
    return f"aimed at {names} roles"


def _skill_facts(scored: ScoredCourse, skill_share: dict[str, float]) -> list[str]:
    def distinctive(skills: tuple[str, ...]) -> list[str]:
        return [s for s in skills if skill_share.get(s, 1.0) <= tuning.DISTINCTIVE_SKILL_MAX_SHARE]

    facts = []
    gaps = distinctive(scored.matched_gap_skills)
    if gaps:
        facts.append(f"builds {_skills_text(gaps)}, a gap for your target role")
    role = distinctive(scored.matched_role_skills)
    if role:
        facts.append(f"covers {_skills_text(role)}, which your target role uses")
    return facts


def _workload(course: Course) -> str | None:
    if course.workload_shape == "lecture_heavy":
        return "taught mostly through lectures and tutorials"
    if course.workload_shape == "project_heavy":
        return "mostly independent project work"
    return None


def _timing(course: Course) -> str | None:
    if not course.offered_terms:
        return "not on this academic year's timetable"
    if len(course.offered_terms) == 1:
        return f"offered only in {course.offered_terms[0]}"
    return None


def _prerequisite(course: Course, cautions: frozenset[str]) -> str | None:
    # An unconfirmed prerequisite is a caution (see the recommendation's
    # `caution`), not a reason.
    if course.prerequisite_text and course.code not in cautions:
        return "its prerequisite is already met"
    return None


def evidence_for(scored: ScoredCourse, slot: RequirementSlot, ctx: EvidenceContext) -> tuple[str, ...]:
    course = scored.course
    facts = [
        _requirement(slot),
        _role_relation(course, slot, ctx.target_role),
        *_skill_facts(scored, ctx.skill_share),
        _workload(course),
        _timing(course),
        _prerequisite(course, ctx.prerequisite_cautions),
    ]
    return tuple(fact for fact in facts if fact)
