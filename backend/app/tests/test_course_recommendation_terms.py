"""Exercises the tool's s2_assembly/terms.py: which regular semester comes
next, and the two ways a term is written."""

from __future__ import annotations

from datetime import date

import pytest

from app.tools.specialist.course_recommendation.s2_assembly import terms
from app.tools.specialist.course_recommendation.s2_assembly.terms import Term


@pytest.mark.parametrize("today, expected", [
    (date(2026, 10, 10), Term(2026, 2)),   # in Semester 1 -> Semester 2
    (date(2027, 2, 1), Term(2027, 1)),     # in Semester 2 -> next AY's Semester 1
    (date(2027, 6, 15), Term(2027, 1)),    # special terms -> the coming Semester 1
    (date(2026, 8, 1), Term(2026, 2)),
])
def test_next_term(today, expected):
    assert terms.next_term(today) == expected


def test_a_named_semester_is_the_first_such_from_the_next_one():
    today = date(2026, 10, 10)
    assert terms.resolve("S2", today) == Term(2026, 2)
    assert terms.resolve("S1", today) == Term(2027, 1)
    assert terms.resolve(None, today) == terms.resolve("next", today) == Term(2026, 2)


def test_labels_round_trip_with_the_student_record():
    term = terms.parse_label("AY2026/27 Sem1")
    assert term == Term(2026, 1)
    assert term.label == "AY2026/27 Sem1" and term.schedule_ay == "2026-2027"
    assert term.following() == Term(2026, 2) and Term(2026, 2).following() == Term(2027, 1)
    assert terms.parse_label("next term") is None
