"""
STAGE 2 (first half) — course catalog classification.

Assigns each course its `requirement_role` (which degree requirement it
would count towards), `level` (4000/5000/6000, parsed from the course
code), and `workload_shape` (which kind of weekly effort it demands) —
the three facts everything downstream (degree progress, requirement slot
derivation, per-slot scoring) is built on.

Pure functions only: no I/O, operates on the primitive facts the upstream
report already supplied (code, vertical tags, workload hours).
"""

from __future__ import annotations

import re

from app.domains.specialist.course_recommendation.models import RequirementRole, WorkloadShape
from app.domains.specialist.course_recommendation.pipeline import curriculum_structure as cs

_CODE_LEVEL = re.compile(r"\d{4}")


def classify_requirement_role(code: str, vertical: tuple[str, ...]) -> RequirementRole:
    """
    Classification order matters — deliberately checks `vertical` before
    core_replacement_candidate. IT5003/IT5004/IT5008 (Vertical #1) and
    IT5005 (Vertical #2) are simultaneously real vertical electives AND
    replacement candidates for BMD5301/IT5001X in the current catalogue.
    Checking replacement-candidate status first would classify them as
    "core_replacement_candidate" and they would never be recommended
    through any requirement slot at all (replacement status alone never
    opens a slot — see degree_progress.py) — they would simply vanish
    from every recommendation. Checking `vertical` first gives them their
    one safe, unconditional role (elective) and keeps the replacement
    possibility as a separate caution note instead of a slot membership.
    """
    if code == cs.CAPSTONE_CODE:
        return "capstone"
    if code in cs.CORE_MANDATORY:
        return "core_mandatory"
    if code in cs.CORE_CHOICE_POOL:
        return "core_choice"
    if vertical:
        return "elective"
    if code in cs.CORE_MANDATORY_REPLACEMENTS:
        return "core_replacement_candidate"
    return "unclassified"


def course_level(code: str) -> int | None:
    """Parses the level (4000/5000/6000/...) from the course code's numeral,
    e.g. CS4221 -> 4000, BT5126 -> 5000. None if the code has no 4-digit run."""
    match = _CODE_LEVEL.search(code)
    if not match:
        return None
    return (int(match.group()) // 1000) * 1000


def workload_shape_of(workload: tuple[float, ...] | None) -> WorkloadShape | None:
    """
    NUSMods' [lecture, tutorial, lab, project, preparation] weekly hours.
    None when no workload data was supplied — this domain never guesses one.
    Total weekly hours are near-uniform across the catalogue (verified: 53
    of 56 recommendable courses cluster at 10-11h/week) so a total-hours
    band carries no signal; the shape of the split does (e.g. FT5007's
    Capstone is 12 of 15 hours independent project work).
    """
    if workload is None or len(workload) != 5:
        return None
    lecture, tutorial, _lab, project, prep = workload
    total = sum(workload)
    if total <= 0:
        return None
    if project / total >= 0.5:
        return "project_heavy"
    if (lecture + tutorial + prep) / total >= 0.7:
        return "lecture_heavy"
    return "balanced"


def is_project_averse(acceptable_workload: str | None) -> bool:
    """Best-effort keyword match over the student's free-text workload
    preference — see curriculum_structure.PROJECT_AVERSE_KEYWORDS. A miss
    here just means the workload-fit scoring term stays neutral, never a
    hard filter."""
    if not acceptable_workload:
        return False
    text = acceptable_workload.strip().lower()
    return any(keyword in text for keyword in cs.PROJECT_AVERSE_KEYWORDS)
