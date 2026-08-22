"""RAG domain models — a single retrieved knowledge-base chunk (see
app/services/rag_service.py)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Hit:
    chunk_key: str
    source_table: str
    content: str
    context: str
    answer_type: str
    conflict_group: str | None
    authoritative: bool
    score: float
    metadata: dict | None = field(default_factory=dict)
    from_vector: bool = False
    from_bm25: bool = False
    topic: str = ""
