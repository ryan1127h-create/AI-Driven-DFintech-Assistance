"""
S6 semester_plan — choosing the semester's courses.

The remaining mandatory core courses that can be taken this semester come
first (fixed); the rest of the unit budget is filled from the other
requirements by trying every combination of their best candidates — the
pools are small, so exhaustive search is cheap and exact. A combination
is valid when it:
  - fits the unit budget (the Capstone counting
    cs.CAPSTONE_UNITS_PER_SEMESTER);
  - takes no more from a requirement than it still needs, and no more
    4000-level electives than can still count;
  - pairs every corequisite: one of its courses done already or in the
    same plan.
Among valid ones, the best has the fewest unavoidable timetable clashes
(two courses meeting at the same time can't both be taken, so a plan
without the clash wins even with fewer units — and the notes say which
courses were kept apart), then uses the most of the budget, then serves
the most pressing requirements, then has the highest scores. A clash no
plan avoids (e.g. between two mandatory courses) stays, flagged, for the
student to decide.

Pure functions, no I/O.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from app.domains.specialist.course_recommendation import timetable
from app.domains.specialist.course_recommendation.models import Pick, PlanContext, PlanPool
from app.domains.specialist.course_recommendation.policy import curriculum as cs

# How much each requirement presses: core courses before electives.
_PRIORITY = {"core_mandatory": 3, "core_choice": 2, "capstone": 2, "elective": 1}
# Best candidates considered per requirement, keeping the search small.
_CANDIDATES_PER_POOL = {"core_choice": 5, "elective": 8, "capstone": 1}
_MAX_ALTERNATIVES = 2


@dataclass(frozen=True)
class Entry:
    """A candidate in a plan, with the requirement it counts toward."""

    pick: Pick
    pool: PlanPool

    @property
    def code(self) -> str:
        return self.pick.scored.course.code

    @property
    def units(self) -> int:
        """Units toward this semester's load."""
        if self.code == cs.CAPSTONE_CODE:
            return cs.CAPSTONE_UNITS_PER_SEMESTER
        return self.pick.scored.course.units


@dataclass(frozen=True)
class Plan:
    entries: tuple[Entry, ...]
    clashes: tuple[tuple[str, str, str], ...]  # (code, code, "Monday 18:30–20:30")

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(e.code for e in self.entries)

    @property
    def units(self) -> int:
        return sum(e.units for e in self.entries)


def _clashes(entries: tuple[Entry, ...], ctx: PlanContext) -> tuple[tuple[str, str, str], ...]:
    term = (ctx.term.ay, ctx.term.semester)
    found = []
    for a, b in itertools.combinations(entries, 2):
        hit = timetable.clash(a.pick.scored.course, b.pick.scored.course, term)
        if hit:
            slot = hit[0]
            found.append((a.code, b.code, f"{slot.day} {slot.start}–{slot.end}"))
    return tuple(found)


def _valid(entries: tuple[Entry, ...], budget: int, ctx: PlanContext) -> bool:
    if sum(e.units for e in entries) > budget:
        return False
    for pool_kind in {e.pool.kind for e in entries}:
        pool = next(e.pool for e in entries if e.pool.kind == pool_kind)
        if sum(1 for e in entries if e.pool.kind == pool_kind) > pool.quota:
            return False
    level4000 = sum(
        1 for e in entries
        if e.pool.kind == "elective" and e.pick.scored.course.level == cs.MIN_COUNTABLE_ELECTIVE_LEVEL
    )
    if level4000 > ctx.level4000_allowance:
        return False
    taken = ctx.done | {e.code for e in entries}
    return all(
        not e.pick.scored.course.corequisite_codes or taken.intersection(e.pick.scored.course.corequisite_codes)
        for e in entries
    )


def _key(plan: Plan) -> tuple:
    score = sum(e.pick.scored.score for e in plan.entries)
    return (-len(plan.clashes), plan.units, sum(_PRIORITY[e.pool.kind] for e in plan.entries), score,
            tuple(sorted(plan.codes)))


def _kept_apart(best: Plan, plans: list[Plan]) -> str | None:
    """A note when avoiding a clash cost units: the fuller plan it beat,
    and the courses that meet at the same time."""
    fuller = next((p for p in plans if p.units > best.units and len(p.clashes) > len(best.clashes)), None)
    if fuller is None:
        return None
    left_out = []
    for a, b, when in fuller.clashes:
        if (a, b, when) in best.clashes:
            continue
        if a not in best.codes and b not in best.codes:
            left_out.append(f"{a} and {b} meet at the same time ({when}), so they can't both be taken")
            continue
        dropped, kept = (a, b) if a not in best.codes else (b, a)
        left_out.append(f"{dropped} is left out: it meets at the same time as {kept} ({when})")
    return "; ".join(dict.fromkeys(left_out)) + "." if left_out else None


def search(pools: tuple[PlanPool, ...], budget: int, ctx: PlanContext) -> tuple[Plan, list[Plan], tuple[str, ...]]:
    """(best plan, up to two alternatives, notes)."""
    notes: list[str] = []
    mandatory = [Entry(p, pool) for pool in pools if pool.kind == "core_mandatory" for p in pool.picks]
    fixed: list[Entry] = []
    for entry in mandatory:  # best-first
        if sum(e.units for e in fixed) + entry.units <= budget:
            fixed.append(entry)
    left_out = [e.code for e in mandatory if e not in fixed]
    if left_out:
        notes.append(
            "Not every remaining mandatory course fits this semester's units; "
            f"{', '.join(left_out)} will need a later semester."
        )

    candidates = [
        Entry(p, pool)
        for pool in pools if pool.kind != "core_mandatory"
        for p in pool.picks[:_CANDIDATES_PER_POOL.get(pool.kind, 5)]
    ]
    room = budget - sum(e.units for e in fixed)
    max_size = max(0, room // cs.TYPICAL_ELECTIVE_UNITS) + 1

    plans: list[Plan] = []
    for size in range(0, min(max_size, len(candidates)) + 1):
        for combo in itertools.combinations(candidates, size):
            entries = tuple(fixed) + combo
            if len({e.code for e in entries}) != len(entries) or not _valid(entries, budget, ctx):
                continue
            plans.append(Plan(entries, _clashes(entries, ctx)))

    plans.sort(key=_key, reverse=True)
    best = plans[0] if plans else Plan(tuple(fixed), _clashes(tuple(fixed), ctx))
    alternatives: list[Plan] = []
    for plan in plans[1:]:
        if len(alternatives) == _MAX_ALTERNATIVES:
            break
        if (plan.units == best.units and len(plan.clashes) <= len(best.clashes)
                and all(len(plan.codes ^ other.codes) >= 2 for other in [best, *alternatives])):
            alternatives.append(plan)
    if best.units < budget:
        notes.append(
            f"Only {best.units} of the {budget} units could be filled with courses open to you "
            "this semester."
        )
        if kept_apart := _kept_apart(best, plans):
            notes.append(kept_apart)
    return best, alternatives, tuple(notes)
