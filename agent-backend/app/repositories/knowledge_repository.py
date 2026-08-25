"""
Knowledge-base repository — pure SQL access (no embedding calls, no BM25, no
fusion logic) to the read-only Supabase knowledge base (`Dfintech-agent-db`,
schema `app`, table `document_chunks`). Only ever issues SELECT statements —
never writes to this database.

See app/services/rag_service.py for the hybrid retrieval (vector + BM25 +
RRF) business logic built on top of this.
"""

from __future__ import annotations

from psycopg.rows import dict_row

from app.clients.postgres_client import LazyPostgresConnection
from app.core.config import settings

APP_SCHEMA = "app"

_conn = LazyPostgresConnection(settings.knowledge_database_url)
_CHUNKS: list[dict] | None = None


def fetch_all_chunks() -> list[dict]:
    """Read all document_chunks into memory once per process (small, static corpus)."""
    global _CHUNKS
    if _CHUNKS is None:
        with _conn.get().cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
                select chunk_key, source_table, content, context,
                       answer_type, conflict_group, authoritative, metadata
                from {APP_SCHEMA}.document_chunks
                order by id
            """)
            _CHUNKS = cur.fetchall()
    return _CHUNKS


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def vector_search_by_embedding(embedding: list[float], k: int) -> list[dict]:
    """Nearest-neighbour search by cosine similarity. Returns raw rows plus
    a `sim` column (1 - cosine distance)."""
    qvec = _to_pgvector(embedding)
    with _conn.get().cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select chunk_key, source_table, content, context, answer_type,
                   conflict_group, authoritative, metadata,
                   1 - (embedding <=> %s::vector) as sim
            from {APP_SCHEMA}.document_chunks
            order by embedding <=> %s::vector
            limit %s
        """, (qvec, qvec, k))
        return cur.fetchall()
