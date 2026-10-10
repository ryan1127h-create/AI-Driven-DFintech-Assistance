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


def _classes_clash(a: tuple[Session, ...], b: tuple[Session, ...]) -> tuple[Session, Session] | None:
    return next(((x, y) for x in a for y in b if overlaps(x, y)), None)


def clash(a: Course, b: Course, term: Term) -> tuple[Session, Session] | None:
    """Two overlapping slots that can't be avoided when taking both
    courses in `term`: some lesson type of each where every class of one
    overlaps every class of the other. None when classes can be chosen
    around it. (Checked one pair of lesson types at a time — enough for
    the programme's timetable, where a lesson type rarely offers more than
    a handful of classes.)"""
    for a_classes in lesson_options(a, term).values():
        for b_classes in lesson_options(b, term).values():
            pairs = [_classes_clash(x, y) for x in a_classes for y in b_classes]
            if pairs and all(pairs):
                return pairs[0]
    return None


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
