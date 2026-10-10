"""
Reading a course's timetable — shared by the stages that need it (S5's
time preferences, S6's clash check), the way models.py is.

A course meets in one or more lesson types (lecture, tutorial, ...). A
lesson type offered in several class numbers is a choice — the student
attends one — so it only forces a time on them when every one of its
classes meets then. Times are "HH:MM" strings, which compare correctly as
text.

Pure functions, no I/O.
"""

from __future__ import annotations

from collections import defaultdict

from app.domains.specialist.course_recommendation.models import Course, Session

# A term as (ay, semester), e.g. ("2026-2027", 2).
Term = tuple[str, int]


def overlaps(a: Session, b: Session) -> bool:
    return a.day == b.day and a.start < b.end and b.start < a.end


def terms_run(course: Course) -> list[Term]:
    """The terms the course has classes in, in order."""
    return sorted({(s.ay, s.semester) for s in course.sessions})


def lesson_options(course: Course, term: Term) -> dict[str, list[tuple[Session, ...]]]:
    """lesson type -> its classes in `term`, each class the slots it meets in."""
    classes: dict[str, dict[str, list[Session]]] = defaultdict(lambda: defaultdict(list))
    for s in course.sessions:
        if (s.ay, s.semester) == term:
            classes[s.lesson_type][s.class_no].append(s)
    return {lesson: [tuple(slots) for slots in by_class.values()] for lesson, by_class in classes.items()}


def _in_windows(slot: Session, windows: tuple[tuple[str, str], ...], days: frozenset[str]) -> bool:
    return slot.day in days or any(slot.start < end and start < slot.end for start, end in windows)


def forced_avoided_slot(
    course: Course, term: Term, windows: tuple[tuple[str, str], ...], days: frozenset[str],
) -> Session | None:
    """A slot in `term` the student can't avoid although it's in a time or
    day they want kept free — some lesson type has every class meeting
    then. None when every lesson type has a class clear of them."""
    for classes in lesson_options(course, term).values():
        hits = [next((s for s in slots if _in_windows(s, windows, days)), None) for slots in classes]
        if hits and all(hits):
            return hits[0]
    return None
