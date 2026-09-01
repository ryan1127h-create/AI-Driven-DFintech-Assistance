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
