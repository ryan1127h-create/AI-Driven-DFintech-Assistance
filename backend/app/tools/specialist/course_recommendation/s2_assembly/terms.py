"""
S2 — the NUS academic calendar, as much of it as planning needs: which
regular semester comes next, and the two ways a term is written (the
student record's "AY2026/27 Sem1", the timetable's ay "2026-2027" with
semester 1).

Semester 1 runs August-December, Semester 2 January-May; the special
terms in between aren't planned for, so from June the next regular
semester is the coming Semester 1.

Pure functions, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_LABEL = re.compile(r"AY\s*(\d{4})\s*/\s*(\d{2,4})\s*Sem\s*([12])", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Term:
    """A regular semester: the academic year it starts in, and 1 or 2."""

    start_year: int
    semester: int

    @property
    def label(self) -> str:
        """As the student record writes it, e.g. "AY2026/27 Sem2"."""
        return f"AY{self.start_year}/{str(self.start_year + 1)[2:]} Sem{self.semester}"

    @property
    def schedule_ay(self) -> str:
        """As the timetable writes the year, e.g. "2026-2027"."""
        return f"{self.start_year}-{self.start_year + 1}"

    def following(self) -> "Term":
        return Term(self.start_year, 2) if self.semester == 1 else Term(self.start_year + 1, 1)


def parse_label(text: str) -> Term | None:
    """"AY2026/27 Sem1" -> Term(2026, 1); None when it isn't a term."""
    match = _LABEL.search(text or "")
    return Term(int(match.group(1)), int(match.group(3))) if match else None


def next_term(today: date) -> Term:
    """The next regular semester to plan for."""
    if today.month >= 8:
        return Term(today.year, 2)
    if today.month <= 5:
        return Term(today.year, 1)
    return Term(today.year, 1)


def resolve(target: str | None, today: date) -> Term:
    """The term a request means: "next" (or nothing) is the next regular
    semester; "S1"/"S2" the first such semester from then on."""
    term = next_term(today)
    if target in ("S1", "S2") and term.semester != int(target[1]):
        term = term.following()
    return term
