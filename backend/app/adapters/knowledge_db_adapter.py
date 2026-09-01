"""
Postgres adapter for KnowledgeBasePort — pure SQL access (no embedding
calls, no ranking logic) to the read-only knowledge-base database (schema
`app`, table `document_chunks`). Only ever issues SELECT statements.

The whole corpus is small and static enough to cache in process for the
adapter's lifetime rather than re-querying per call.
"""

from __future__ import annotations

import threading

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.ports.knowledge_base_port import KnowledgeBasePort

_APP_SCHEMA = "app"


class KnowledgeDBAdapter(KnowledgeBasePort):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._conn_lock = threading.Lock()
        self._chunks: list[dict] | None = None
        self._chunks_lock = threading.Lock()
        self._courses: list[dict] | None = None
        self._courses_lock = threading.Lock()

    def _get_conn(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            with self._conn_lock:
                if self._conn is None or self._conn.closed:
                    self._conn = psycopg.connect(self._dsn, connect_timeout=5)
        return self._conn

    def fetch_all_chunks(self) -> list[dict]:
        if self._chunks is None:
            with self._chunks_lock:
                if self._chunks is None:
                    with self._get_conn().cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            f"""
                            select chunk_key, source_table, content, context,
                                   answer_type, conflict_group, authoritative, metadata
                            from {_APP_SCHEMA}.document_chunks
                            order by id
                            """
                        )
                        self._chunks = cur.fetchall()
        return self._chunks

    def fetch_all_courses(self) -> list[dict]:
        if self._courses is None:
            with self._courses_lock:
                if self._courses is None:
                    with self._get_conn().cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            f"""
                            select course_code, title, annex_title, nusmods_title,
                                   annex_presence, annex_section, module_credit,
                                   faculty, department, description, prerequisite,
                                   corequisite, preclusion, semester_count, source_url
                            from {_APP_SCHEMA}.courses
                            order by course_code
                            """
                        )
                        self._courses = cur.fetchall()
        return self._courses

    @staticmethod
    def _to_pgvector(vec: list[float]) -> str:
        return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"

    def vector_search_by_embedding(self, embedding: list[float], k: int) -> list[dict]:
        qvec = self._to_pgvector(embedding)
        with self._get_conn().cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select chunk_key, source_table, content, context, answer_type,
                       conflict_group, authoritative, metadata,
                       1 - (embedding <=> %s::vector) as sim
                from {_APP_SCHEMA}.document_chunks
                order by embedding <=> %s::vector
                limit %s
                """,
                (qvec, qvec, k),
            )
            return cur.fetchall()


knowledge_db = KnowledgeDBAdapter(settings.knowledge_database_url)
