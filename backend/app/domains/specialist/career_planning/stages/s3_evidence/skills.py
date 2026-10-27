"""
S3 — grades every role skill from the student's evidence, by the signals
in policy/skill_evidence.py. Pure code, no LLM, no I/O.

Per skill, each source (a profile field, or the courses) contributes its
best-matching signal once; the points add up to the status:

    met      points reach MET_POINTS
    partial  some points, fewer than that
    missing  no points, and the profile explicitly says the skill isn't there
    unknown  nothing either way

Every graded skill carries the evidence it rests on, so a reply can cite
it and a reader can check it.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domains.specialist.career_planning.models import (
    CourseLink,
    EvidenceItem,
    SkillAssessment,
    StudentEvidence,
)
from app.domains.specialist.career_planning.policy import skill_evidence as rules
from app.domains.specialist.career_planning.policy.skill_evidence import Signal

_ABSENT = object()


def course_tags(links: tuple[CourseLink, ...]) -> dict[str, frozenset[str]]:
    """Course code -> the role tags it carries."""
    return {link.code: link.tags for link in links}


def _level_item(signal: Signal, evidence: StudentEvidence) -> EvidenceItem | None:
    value = evidence.facts.get(signal.field)
    points = dict(signal.levels).get(value) if isinstance(value, int) else None
    return EvidenceItem(signal.field, (str(value),), points) if points else None


def _function_item(signal: Signal, evidence: StudentEvidence) -> EvidenceItem | None:
    """Full points for work experience, a share for internship-only."""
    matches = [f for f in evidence.functions if f.key in signal.values]
    if not matches:
        return None
    if any(not f.internship for f in matches):
        keys = tuple(dict.fromkeys(f.key for f in matches if not f.internship))
        return EvidenceItem(signal.field, keys, signal.points)
    keys = tuple(dict.fromkeys(f.key for f in matches))
    return EvidenceItem(signal.field, keys, signal.points * rules.INTERNSHIP_FACTOR, internship=True)


def _any_of_item(signal: Signal, evidence: StudentEvidence) -> EvidenceItem | None:
    if signal.field == "function_experience":
        return _function_item(signal, evidence)
    value = evidence.facts.get(signal.field)
    values = value if isinstance(value, tuple) else (value,) if isinstance(value, str) else ()
    matched = tuple(v for v in values if v in signal.values)
    return EvidenceItem(signal.field, matched, signal.points) if matched else None


def _course_item(
    signal: Signal, evidence: StudentEvidence, tags: Mapping[str, frozenset[str]],
) -> EvidenceItem | None:
    """Each matching course adds the signal's points weighted by its tag
    count, up to the signal's points. Completed courses count in full;
    only if none match, current ones count at a share."""
    def matching(codes):
        return tuple(c for c in codes if tags.get(c, frozenset()) & signal.values)

    def points(codes):
        total = sum(signal.points * rules.course_weight(len(tags[c])) for c in codes)
        return round(min(total, signal.points), 6)

    done = matching(evidence.completed_courses)
    if done:
        return EvidenceItem("courses", done, points(done))
    taking = matching(evidence.current_courses)
    if taking:
        return EvidenceItem("courses", taking, round(points(taking) * rules.IN_PROGRESS_FACTOR, 6), in_progress=True)
    return None


def _match(signal: Signal, evidence: StudentEvidence, tags: Mapping[str, frozenset[str]]):
    if signal.kind == "level":
        return _level_item(signal, evidence)
    if signal.kind == "any_of":
        return _any_of_item(signal, evidence)
    if signal.kind == "course_tag":
        return _course_item(signal, evidence, tags)
    value = evidence.facts.get(signal.field)
    return _ABSENT if value in dict(signal.levels) else None


def assess_skill(
    skill: str, evidence: StudentEvidence, tags: Mapping[str, frozenset[str]],
) -> SkillAssessment:
    best: dict[str, EvidenceItem] = {}
    absent = False
    for signal in rules.SKILL_SIGNALS[skill]:
        item = _match(signal, evidence, tags)
        if item is _ABSENT:
            absent = True
        elif item is not None and (signal.field not in best or item.points > best[signal.field].points):
            best[signal.field] = item

    items = tuple(sorted(best.values(), key=lambda i: -i.points))
    points = round(min(sum(i.points for i in items), rules.MET_POINTS), 6)
    if points >= rules.MET_POINTS:
        status = "met"
    elif points > 0:
        status = "partial"
    else:
        status = "missing" if absent else "unknown"
    return SkillAssessment(skill=skill, status=status, points=points, evidence=items)


def assess_skills(
    evidence: StudentEvidence, links: tuple[CourseLink, ...],
) -> dict[str, SkillAssessment]:
    """Every skill in the vocabulary, graded."""
    tags = course_tags(links)
    return {skill: assess_skill(skill, evidence, tags) for skill in rules.SKILLS}


def has_any_evidence(assessments: Mapping[str, SkillAssessment]) -> bool:
    return any(a.status != "unknown" for a in assessments.values())
