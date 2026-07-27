"""Pluggable retrieval backends (design doc 12 §3).

Retriever is the seam for swapping models when delivering to the school: today
a local BM25 backend (offline, deterministic) and an OpenAI-compatible
embedding backend (added in a later task). Both return confidence.RetrievalChunk
so the existing decide() gate is unchanged.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Protocol

from common.confidence import RetrievalChunk, _tokens
from common.knowledge import KnowledgeChunk, load_knowledge
from common import config, embeddings


class Retriever(Protocol):
    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]: ...


def _to_chunk(kc: KnowledgeChunk, score: float) -> RetrievalChunk:
    return RetrievalChunk(text=kc.text, source_id=kc.source_id, score=round(score, 4))


class BM25Retriever:
    """Lexical retriever over the curated KB using BM25-style IDF weighting.

    Scores a chunk by **IDF-weighted query coverage**: the share of the query's
    information (each term weighted by rarity) that the chunk covers. The score is
    absolute in [0,1] — crucially NOT max-normalised against the current query, so
    an off-topic query that only matches common stopwords scores low instead of a
    spurious 1.0. That keeps the downstream confidence gate meaningful and gives
    the threshold calibration a real signal to work with. Pure stdlib, deterministic.
    """

    def __init__(self) -> None:
        self._chunks = load_knowledge()
        self._docs = {c.id: set(_tokens(c.text)) for c in self._chunks}
        n = len(self._chunks) or 1
        df: Counter[str] = Counter()
        for toks in self._docs.values():
            for t in toks:
                df[t] += 1
        self._idf = {
            t: math.log(1 + (n - dfi + 0.5) / (dfi + 0.5)) for t, dfi in df.items()
        }
        # Unseen query terms are treated as maximally rare (df=0): an off-topic
        # word like "weather" carries high IDF in the denominator but matches
        # nothing, pulling the coverage score down.
        self._unseen_idf = math.log(1 + (n + 0.5) / 0.5)

    def _idf_of(self, term: str) -> float:
        return self._idf.get(term, self._unseen_idf)

    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]:
        q_terms = set(_tokens(query))
        if not q_terms:
            return []
        denom = sum(self._idf_of(t) for t in q_terms)
        if denom == 0:
            return []
        pool = [c for c in self._chunks
                if namespace is None or c.namespace == namespace]
        scored: list[tuple[KnowledgeChunk, float]] = []
        for c in pool:
            dtoks = self._docs[c.id]
            num = sum(self._idf_of(t) for t in q_terms if t in dtoks)
            s = num / denom
            if s > 0:
                scored.append((c, s))
        if not scored:
            return []
        scored.sort(key=lambda cs: cs[1], reverse=True)
        return [_to_chunk(c, min(1.0, s)) for c, s in scored[:top_k]]


_KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"


def _cache_path() -> Path:
    return _KB_DIR / "_embeddings.json"


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


class EmbeddingRetriever:
    """OpenAI-compatible embedding retrieval with a fingerprinted vector cache.

    Chunk vectors are embedded once and cached; the cache is rebuilt whenever the
    embedding model fingerprint changes (never mixes vectors across models).
    """

    def __init__(self) -> None:
        self._chunks = load_knowledge()
        self._model = config.get_embedding_model()
        self._vectors = self._load_or_build_cache()

    def _load_or_build_cache(self) -> dict[str, list[float]]:
        path = _cache_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("model") == self._model:
                    return data.get("vectors", {})
            except (json.JSONDecodeError, OSError):
                pass
        vecs = embeddings.embed_texts([c.text for c in self._chunks])
        vectors = {c.id: v for c, v in zip(self._chunks, vecs)}
        dim = len(vecs[0]) if vecs else 0
        try:
            path.write_text(
                json.dumps({"model": self._model, "dim": dim, "vectors": vectors}),
                encoding="utf-8",
            )
        except OSError:
            pass
        return vectors

    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]:
        if not query.strip():
            return []
        qv = embeddings.embed_texts([query])[0]
        pool = [c for c in self._chunks
                if namespace is None or c.namespace == namespace]
        scored = [(c, _cosine(qv, self._vectors[c.id]))
                  for c in pool if c.id in self._vectors]
        scored.sort(key=lambda cs: cs[1], reverse=True)
        return [_to_chunk(c, s) for c, s in scored[:top_k]]


def get_retriever() -> Retriever:
    """Pick a backend: embedding when configured+usable, else offline BM25.

    EmbeddingRetriever is wired in a later task; until then this returns BM25.
    """
    import os

    from common import config

    # 整合:接入队友(数据+检索)的四层检索(Supabase pgvector + BM25 + RRF + Cohere rerank)。
    # 设 USE_SUPABASE_RETRIEVER=1 时启用;不设则维持原来的 BM25，可随时切回。
    # 适配器 rag_backend/retrieval_api.py 实现了本文件的 Retriever Protocol。
    if os.getenv("USE_SUPABASE_RETRIEVER", "").strip() in ("1", "true", "True"):
        try:
            from rag_backend.retrieval_api import SupabaseRetriever

            return SupabaseRetriever()
        except Exception as e:  # 连不上/缺依赖 -> 安全回落到离线 BM25
            print(f"[get_retriever] Supabase 检索不可用，回落 BM25: {e}")

    if config.is_configured():
        try:
            from common.embeddings import embedding_available

            if embedding_available():
                return EmbeddingRetriever()
        except Exception:
            pass  # fail safe -> offline backend
    return BM25Retriever()
