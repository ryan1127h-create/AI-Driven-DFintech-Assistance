"""
Postgres adapter for KnowledgeBasePort — pure SQL access (no embedding
calls, no ranking logic) to the read-only knowledge-base schema
`knowledge`: the retrieval chunks (document_chunks), the course catalogue
(split across courses and its per-course detail tables), the role tags,
the admissions items and the application status explanations. Owned by
app/domains/knowledge_retrieval/service.py; only ever issues SELECT
statements, over the connection pool shared with the other schema
adapters (see postgres_pool.py).

The whole corpus is small and static enough to cache in process for the
adapter's lifetime rather than re-querying per call.
"""

from __future__ import annotations

import threading
from typing import Callable

from app.adapters.postgres_pool import SchemaDB, pool
from app.ports.knowledge_base_port import KnowledgeBasePort

_APP_SCHEMA = "knowledge"

# One row per course. The per-course detail tables are 1:1 with courses
# except course_schedule (one row per class slot), which is folded into the
# semesters the course runs in during the latest academic year on file.
_COURSES_SQL = f"""
    select c.course_code, c.title, c.annex_section, c.annex_intake, c.module_credit,
           cd.description,
           cd.desc_review is not null as needs_review,
           cm.source_url,
           c.status = 'active' as can_recommend,
           case when w.course_code is null then null
                else array[w.workload_lecture, w.workload_tutorial, w.workload_lab,
                           w.workload_project, w.workload_prep]
           end as workload,
           r.prerequisite as prerequisite_grad_text,
           null::text as corequisite_grad_text,
           coalesce(array(select trim(x) from unnest(string_to_array(r.preclusion, ';')) x
                           where trim(x) <> ''), '{{}}') as preclusion_codes,
           s.ay as current_ay_label,
           coalesce(s.semesters, '{{}}') as current_ay_semesters
      from {_APP_SCHEMA}.courses c
      left join {_APP_SCHEMA}.course_descriptions cd on cd.course_code = c.course_code
      left join {_APP_SCHEMA}.course_meta cm on cm.course_code = c.course_code
      left join {_APP_SCHEMA}.course_workload w on w.course_code = c.course_code
      left join {_APP_SCHEMA}.course_requirements r on r.course_code = c.course_code
      left join lateral (
          select cs.ay, array_agg(distinct cs.semester::int order by cs.semester::int) as semesters
            from {_APP_SCHEMA}.course_schedule cs
           where cs.course_code = c.course_code
             and cs.ay = (select max(ay) from {_APP_SCHEMA}.course_schedule)
             and cs.semester ~ '^[0-9]+$'
           group by cs.ay
      ) s on true
     order by c.course_code
"""


class KnowledgeDBAdapter(KnowledgeBasePort):
    def __init__(self, db: SchemaDB) -> None:
        self._db = db
        self._cache: dict[str, list[dict]] = {}
        self._cache_lock = threading.Lock()

    @property
    def schema(self) -> str:
        return self._db.schema

    def _query(self, sql: str, params=()) -> list[dict]:
        return self._db.fetch_all_dict(sql, params)

    def _cached(self, key: str, load: Callable[[], list[dict]]) -> list[dict]:
        if key not in self._cache:
            with self._cache_lock:
                if key not in self._cache:
                    self._cache[key] = load()
        return self._cache[key]

    def fetch_all_chunks(self) -> list[dict]:
        return self._cached("chunks", lambda: self._query(
            f"""
            select chunk_key, source_table, content, context,
                   answer_type, conflict_group, authoritative, metadata
            from {_APP_SCHEMA}.document_chunks
            order by id
            """
        ))

    def fetch_all_courses(self) -> list[dict]:
        return self._cached("courses", lambda: self._query(_COURSES_SQL))

    def fetch_course_electives(self) -> list[dict]:
        return self._cached("course_electives", lambda: self._query(
            f"select course_code, vertical from {_APP_SCHEMA}.course_electives"
        ))

    def fetch_course_schedule(self) -> list[dict]:
        return self._cached("course_schedule", lambda: self._query(
            f"""
            select course_code, ay, semester, lesson_type, class_no, day, start_time, end_time
              from {_APP_SCHEMA}.course_schedule
             where semester ~ '^[0-9]+$'
             order by course_code, ay, semester, lesson_type, class_no, day, start_time
            """
        ))

    def fetch_role_tags(self) -> list[dict]:
        return self._cached("role_tags", lambda: self._query(
            f"select tag, name_en, name_zh, definition, required_skills from {_APP_SCHEMA}.tags_definition order by tag"
        ))

    def fetch_course_tags(self) -> list[dict]:
        return self._cached("course_tags", lambda: self._query(
            f"select course_code, tag from {_APP_SCHEMA}.course_tags order by course_code, tag"
        ))

    def fetch_admissions_items(self) -> list[dict]:
        return self._cached("admissions_items", lambda: self._query(
            f"select key, label, why, required from {_APP_SCHEMA}.admissions_items order by key"
        ))

    def fetch_status_translations(self) -> list[dict]:
        return self._cached("status_translations", lambda: self._query(
            f"select status_code, human_status, next_step from {_APP_SCHEMA}.application_status_translations"
        ))

    @staticmethod
    def _to_pgvector(vec: list[float]) -> str:
        return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"

    def vector_search_by_embedding(self, embedding: list[float], k: int) -> list[dict]:
        qvec = self._to_pgvector(embedding)
        return self._query(
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


knowledge_db = KnowledgeDBAdapter(SchemaDB("knowledge", pool))
