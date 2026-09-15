"""
Contract for read-only access to the shared knowledge base — the document
chunks (courses, career roles, curriculum rules, programme pages, FAQ
content, ...) every retrieval-driven domain reads from.
"""

from __future__ import annotations

from typing import Protocol


class KnowledgeBasePort(Protocol):
    def fetch_all_chunks(self) -> list[dict]:
        """Returns every chunk in the corpus (small and static enough to
        load in full — callers that need a subset filter it themselves)."""
        ...

    def vector_search_by_embedding(self, embedding: list[float], k: int) -> list[dict]:
        """Nearest-neighbour search by cosine similarity. Returns the top-k
        chunks plus a `sim` key (1 - cosine distance) on each."""
        ...

    def fetch_all_courses(self) -> list[dict]:
        """Returns every row of the raw course catalog (schema `app`, table
        `courses`) — the source table course_recommendation's chunk-based
        retrieval is itself derived from. Unrelated to fetch_all_chunks()."""
        ...

    def fetch_module_skills(self) -> list[dict]:
        """Returns every (module_code, skill_id) row from the course-skill
        tagging table — a many-to-many join callers group by module_code
        themselves; a course with no tagged skills simply has no rows here."""
        ...

    def fetch_career_role_modules(self, role_id: str) -> list[dict]:
        """Returns the domain-expert-curated, priority-ordered course list
        for one career role (role_id/course_code/module_name/position),
        ordered by position. Empty list if the role has no curated list."""
        ...

    def fetch_course_electives(self) -> list[dict]:
        """Returns every (course_code, vertical) elective-track membership.
        A course can belong to more than one vertical — unlike the
        single-valued `annex_section` column on courses, this is where a
        course's full elective membership (including a core-replacement
        course that's also a vertical elective) lives."""
        ...
