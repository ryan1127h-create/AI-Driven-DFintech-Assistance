"""
Where a programme's application rounds stand on a given day. A round with
no published opening date counts as open until it closes — programmes
that omit the date usually take applications already.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RoundStatus:
    round_no: int
    label: str | None
    opens_on: date | None
    closes_on: date
    status: str  # "closed" | "open" | "upcoming"
    days_left: int | None  # until it closes, for an open round


@dataclass(frozen=True)
class DeadlineStatus:
    rounds: tuple[RoundStatus, ...]
    # The open round closing soonest, else the next to open.
    next_round: RoundStatus | None

    @property
    def all_closed(self) -> bool:
        return bool(self.rounds) and self.next_round is None


def _status(opens_on: date | None, closes_on: date, today: date) -> str:
    if today > closes_on:
        return "closed"
    if opens_on and today < opens_on:
        return "upcoming"
    return "open"


def status(rounds: list[dict], today: date) -> DeadlineStatus:
    """`rounds`: [{round_no, round_label, opens_on, closes_on}] for one
    applicant category."""
    items = []
    for r in sorted(rounds, key=lambda r: (r["closes_on"], r["round_no"])):
        state = _status(r.get("opens_on"), r["closes_on"], today)
        days = (r["closes_on"] - today).days if state == "open" else None
        items.append(RoundStatus(r["round_no"], r.get("round_label"), r.get("opens_on"), r["closes_on"], state, days))
    open_rounds = [r for r in items if r.status == "open"]
    upcoming = [r for r in items if r.status == "upcoming"]
    nxt = open_rounds[0] if open_rounds else (min(upcoming, key=lambda r: r.opens_on) if upcoming else None)
    return DeadlineStatus(tuple(items), nxt)
