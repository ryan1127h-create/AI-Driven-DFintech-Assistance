"""
Contract for read-only access to the shared knowledge base — the document
chunks (courses, role tags, curriculum rules, programme pages, FAQ
content, ...) every retrieval-driven domain reads from, plus the
structured course catalogue and role tags behind them.
"""

from __future__ import annotations

from typing import Protocol


class KnowledgeBasePort(Protocol):
    def invalidate(self) -> None:
        """Drops whatever the adapter has cached, so the next read sees
        rows edited since (the staff console's knowledge editor)."""
        ...

    def fetch_all_chunks(self) -> list[dict]:
        """Returns every chunk in the corpus (small and static enough to
        load in full — callers that need a subset filter it themselves)."""
        ...

    def vector_search_by_embedding(self, embedding: list[float], k: int) -> list[dict]:
        """Nearest-neighbour search by cosine similarity. Returns the top-k
        chunks plus a `sim` key (1 - cosine distance) on each."""
        ...

    def fetch_all_courses(self) -> list[dict]:
        """Returns one row per course of the catalogue, assembled from the
        course tables (courses + descriptions, meta, requirements,
        workload, schedule). Unrelated to fetch_all_chunks()."""
        ...

    def fetch_course_electives(self) -> list[dict]:
        """Returns every (course_code, vertical) elective-track membership.
        A course can belong to more than one vertical — unlike the
        single-valued `annex_section` column on courses, this is where a
        course's full elective membership (including a core-replacement
        course that's also a vertical elective) lives."""
        ...

    def fetch_course_schedule(self) -> list[dict]:
        """Returns every class slot on file (course_code, ay, semester,
        lesson_type, class_no, day, start_time, end_time) for the regular
        semesters, times as "HHMM"."""
        ...

    def fetch_role_tags(self) -> list[dict]:
        """Returns every role tag (tag, name_en, definition,
        required_skills) — the 12 role families courses and profiles use."""
        ...

    def fetch_course_tags(self) -> list[dict]:
        """Returns every (course_code, tag) row; every course has at least
        one tag."""
        ...

    def fetch_admissions_items(self) -> list[dict]:
        """Returns every admissions document item (key, label, why,
        required)."""
        ...

    def fetch_status_translations(self) -> list[dict]:
        """Returns every application status explanation (status_code,
        human_status, next_step)."""
        ...
