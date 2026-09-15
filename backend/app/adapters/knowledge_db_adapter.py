"""
Postgres adapter for KnowledgeBasePort — pure SQL access (no embedding
calls, no ranking logic) to the read-only knowledge-base database (schema
`knowledge`, table `document_chunks`). Only ever issues SELECT statements.

The whole corpus is small and static enough to cache in process for the
adapter's lifetime rather than re-querying per call.
"""

from __future__ import annotations

import threading

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.ports.knowledge_base_port import KnowledgeBasePort

_APP_SCHEMA = "knowledge"


class KnowledgeDBAdapter(KnowledgeBasePort):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._conn_lock = threading.Lock()
        self._chunks: list[dict] | None = None
        self._chunks_lock = threading.Lock()
        self._courses: list[dict] | None = None
        self._courses_lock = threading.Lock()
        self._module_skills: list[dict] | None = None
        self._module_skills_lock = threading.Lock()
        self._course_electives: list[dict] | None = None
        self._course_electives_lock = threading.Lock()

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
                            select course_code, title, annex_section, module_credit,
                                   faculty, department, description, source_url,
                                   can_recommend, needs_review, workload,
                                   prerequisite_grad_text, corequisite_grad_text,
                                   preclusion_codes, current_ay_label, current_ay_semesters
                            from {_APP_SCHEMA}.courses
                            order by course_code
                            """
                        )
                        self._courses = cur.fetchall()
        return self._courses

    def fetch_module_skills(self) -> list[dict]:
        if self._module_skills is None:
            with self._module_skills_lock:
                if self._module_skills is None:
                    with self._get_conn().cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            f"select module_code, skill_id from {_APP_SCHEMA}.module_skills"
                        )
                        self._module_skills = cur.fetchall()
        return self._module_skills

    def fetch_career_role_modules(self, role_id: str) -> list[dict]:
        # career_role_modules has no module_name column of its own — the
        # display title is joined live from courses.title so it can never
        # drift out of sync with a course's own record (see the
        # table-simplification note: module_name used to duplicate this
        # verbatim, with zero divergence found before it was dropped).
        with self._get_conn().cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select crm.role_id, crm.course_code, c.title as module_name, crm.position
                from {_APP_SCHEMA}.career_role_modules crm
                join {_APP_SCHEMA}.courses c on c.course_code = crm.course_code
                where crm.role_id = %s
                order by crm.position
                """,
                (role_id,),
            )
            return cur.fetchall()

    def fetch_course_electives(self) -> list[dict]:
        if self._course_electives is None:
            with self._course_electives_lock:
                if self._course_electives is None:
                    with self._get_conn().cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            f"select course_code, vertical from {_APP_SCHEMA}.course_electives"
                        )
                        self._course_electives = cur.fetchall()
        return self._course_electives

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


knowledge_db = KnowledgeDBAdapter(settings.database_url)
