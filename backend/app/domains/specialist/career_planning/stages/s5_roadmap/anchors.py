"""
S5 — the dates a roadmap hangs on, from the student's situation and
policy/calendar.py. Pure code, no I/O.

  - programme start: for a student not yet in the programme, the next
    August intake (an admitted student in August-December has just
    started);
  - the Capstone cycle: the one ending before graduation, else (no
    graduation term) for a student before the programme the cycle after
    their intake year (full-time pace), for anyone else the next one still
    taking applications;
  - graduation: the record's expected term, else estimated as the
    semester the Capstone internship ends in (full-time pace).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domains.specialist.career_planning.models import RoadmapContext
from app.domains.specialist.career_planning.policy import calendar
from app.domains.specialist.career_planning.policy.calendar import CapstoneCycle, Term

PRE_PROGRAMME_STAGES = frozenset({"prospect", "applicant", "admitted"})


@dataclass(frozen=True)
class Anchors:
    pre_programme: bool
    programme_start: date | None
    cycle: CapstoneCycle
    graduation: Term
    graduation_estimated: bool


def programme_start(ctx: RoadmapContext) -> date | None:
    if ctx.stage not in PRE_PROGRAMME_STAGES:
        return None
    this_year = date(ctx.today.year, 8, 1)
    if ctx.today < this_year or ctx.stage == "admitted":
        return this_year
    return date(ctx.today.year + 1, 8, 1)


def resolve(ctx: RoadmapContext) -> Anchors:
    start = programme_start(ctx)
    pre = start is not None and start > ctx.today
    graduation = calendar.parse_term(ctx.expected_grad_term)
    if graduation is not None:
        cycle = calendar.cycle_before_graduation(graduation)
    elif start is not None:
        cycle = calendar.capstone_cycle(start.year + 1)
    else:
        cycle = calendar.next_open_cycle(ctx.today)
    estimated = graduation is None
    if estimated:
        graduation = Term(cycle.year, 1)
    return Anchors(
        pre_programme=pre,
        programme_start=start if pre else None,
        cycle=cycle,
        graduation=graduation,
        graduation_estimated=estimated,
    )
