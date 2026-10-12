"""
S3 — structured prerequisites and timetable availability, checked against
what the student has done and the semester being planned.

A course's prerequisite_groups must all be met, each by any one of its
courses (see contracts.PrerequisitesInput). Corequisites aren't checked
here: one may be taken in the same semester, which only the semester
planner (S6) can see.

Pure functions, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import Course, PlanTerm


def unmet_groups(course: Course, done: set[str]) -> tuple[tuple[str, ...], ...]:
    """The prerequisite groups none of whose courses is done."""
    return tuple(group for group in course.prerequisite_groups if not done.intersection(group))


def describe_group(group: tuple[str, ...]) -> str:
    """("IT5001", "IT5001X") -> "IT5001 or IT5001X"."""
    return " or ".join(group)


def timetable_known(courses: list[Course], term: PlanTerm) -> bool:
    """Whether the timetable for `term` is on file at all — without it, no
    course can be said not to run then."""
    return any(s.ay == term.ay and s.semester == term.semester for c in courses for s in c.sessions)


def runs_in(course: Course, term: PlanTerm) -> bool:
    return any(s.ay == term.ay and s.semester == term.semester for s in course.sessions)
