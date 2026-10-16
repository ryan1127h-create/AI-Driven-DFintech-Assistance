"""
S5 dates — the programme's regular semesters and the Capstone internship
cycle, as the roadmap's time anchors.

Semesters follow NUS's academic year: Semester 1 runs August-December,
Semester 2 January-May; June-July are special terms. Terms are written as
the student record writes them, "AY2027/28 Sem1".

The Capstone cycle is transcribed from the programme's Capstone page
(knowledge.programme_pages, label 'Capstone Project'), which gives the
2027 cycle only: student applications 1 Dec 2026 - 31 Mar 2027, offers by
15 Apr 2027, internship 17 May - 15 Oct 2027 (at least 16 weeks, located
in Singapore, IT/computing related). Other years repeat those dates and
are marked projected — the school publishes each cycle's dates itself.
Update REFERENCE_CYCLE_YEAR and the dates together when a newer cycle's
page is ingested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

CAPSTONE_LOCATION = "SG"  # target_markets key for Singapore

REFERENCE_CYCLE_YEAR = 2027
# (month, day) of each Capstone date in its cycle year; applications open
# in December of the year before.
_APPLICATIONS_OPEN = (12, 1)
_APPLICATIONS_CLOSE = (3, 31)
_OFFERS_BY = (4, 15)
_INTERNSHIP_START = (5, 17)
_INTERNSHIP_END = (10, 15)

_TERM_LABEL = re.compile(r"^AY(\d{4})/(\d{2}) Sem([12])$")


@dataclass(frozen=True, order=True)
class Term:
    """A regular semester: `year` is the academic year's first calendar
    year (AY2027/28 -> 2027)."""

    year: int
    semester: int

    @property
    def label(self) -> str:
        return f"AY{self.year}/{(self.year + 1) % 100:02d} Sem{self.semester}"

    @property
    def start(self) -> date:
        return date(self.year, 8, 1) if self.semester == 1 else date(self.year + 1, 1, 1)

    @property
    def end(self) -> date:
        return date(self.year, 12, 31) if self.semester == 1 else date(self.year + 1, 5, 31)

    def following(self) -> "Term":
        return Term(self.year, 2) if self.semester == 1 else Term(self.year + 1, 1)


def parse_term(label: str | None) -> Term | None:
    match = _TERM_LABEL.match(label.strip()) if isinstance(label, str) else None
    if not match:
        return None
    year, next_year, semester = int(match[1]), int(match[2]), int(match[3])
    if (year + 1) % 100 != next_year:
        return None
    return Term(year, semester)


@dataclass(frozen=True)
class CapstoneCycle:
    year: int
    applications_open: date
    applications_close: date
    offers_by: date
    internship_start: date
    internship_end: date
    # True when the dates repeat the reference cycle's rather than being
    # the school's published dates for this year.
    projected: bool


def capstone_cycle(year: int) -> CapstoneCycle:
    return CapstoneCycle(
        year=year,
        applications_open=date(year - 1, *_APPLICATIONS_OPEN),
        applications_close=date(year, *_APPLICATIONS_CLOSE),
        offers_by=date(year, *_OFFERS_BY),
        internship_start=date(year, *_INTERNSHIP_START),
        internship_end=date(year, *_INTERNSHIP_END),
        projected=year != REFERENCE_CYCLE_YEAR,
    )


def next_open_cycle(today: date) -> CapstoneCycle:
    """The first cycle whose applications haven't closed by `today`."""
    year = today.year if today <= date(today.year, *_APPLICATIONS_CLOSE) else today.year + 1
    return capstone_cycle(year)


def cycle_before_graduation(graduation: Term) -> CapstoneCycle:
    """The last cycle whose internship ends by the graduation term's end —
    the one a student graduating then would do."""
    end = graduation.end
    year = end.year if end >= date(end.year, *_INTERNSHIP_END) else end.year - 1
    return capstone_cycle(year)
