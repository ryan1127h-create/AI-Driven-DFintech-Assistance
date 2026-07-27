"""Curated knowledge base loader (research roadmap A / design doc 12 §3.1).

Chunks live in data/knowledge/*.jsonl, one JSON object per line. The retriever
layer consumes these; nothing here calls an LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    namespace: str  # admissions | curriculum | faq
    text: str
    source_id: str
    source_type: str  # official | advisory


def load_knowledge(namespace: str | None = None) -> list[KnowledgeChunk]:
    """Load curated chunks, optionally filtered to one namespace."""
    chunks: list[KnowledgeChunk] = []
    for path in sorted(_KB_DIR.glob("*.jsonl")):
        if path.name.startswith("_"):
            continue  # skip caches like _embeddings.json analogues
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            chunk = KnowledgeChunk(
                id=d["id"], namespace=d["namespace"], text=d["text"],
                source_id=d["source_id"], source_type=d["source_type"],
            )
            if namespace is None or chunk.namespace == namespace:
                chunks.append(chunk)
    return chunks
