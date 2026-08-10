"""
RAG service — hybrid retrieval (vector + BM25 + RRF) against the knowledge
base repository, with a Redis result cache in front, plus the prompt-context
and citation formatting used by every RAG-backed agent.

Any future module that wants RAG-grounded answers only needs:
    from app.services.rag_service import retrieve, build_context, cited_sources

The knowledge base data and its embeddings are produced by a separate
project (see data_process/rag-backend). Retrieval only ever issues SELECT
statements against the knowledge database (see
app/repositories/knowledge_repository.py) — it never writes to it.

Query-time embedding uses the same model the chunks were embedded with
(OpenAI text-embedding-3-small, 1536 dims) — using a different model here
would put queries and stored vectors in different vector spaces, making
cosine similarity meaningless.

Cohere rerank is intentionally not used here (see plan): its evaluated
marginal gain was small and its rate limit does not fit a multi-user
backend. Adding it back later only means adding one more stage to
`retrieve()`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict

from app.clients.openai_client import embed_text
from app.clients.redis_client import get_redis_client
from app.core.config import settings
from app.models.rag import Hit
from app.repositories.knowledge_repository import fetch_all_chunks, vector_search_by_embedding

# RRF weights: semantic-first, keyword as a booster for codes/numbers that
# embeddings tend to blur together (e.g. FT5005 vs FT5009).
W_SEMANTIC = 0.8
W_BM25 = 0.2

# Each of vector/BM25 first pulls this many candidates for RRF to fuse.
# 50 is generous relative to the corpus size (~184 chunks).
RECALL_K = 50

# Score multiplier applied to hits whose topic is in an agent's boost_topics,
# after RRF fusion. A soft nudge, not a hard filter — see plan Phase 3 for
# why admissions/academic/financial/faq use boosting rather than filtering.
TOPIC_BOOST_FACTOR = 1.3

_CACHE_KEY_PREFIX = "rag:retrieve:"

# Maps a document_chunks row to one of the topic buckets agents filter/boost
# by. Grounded in the actual data (see plan Phase 3): source_table alone is
# enough for most tables; knowledge_snippets and programme_pages need a
# metadata field to disambiguate since they mix topics internally.
_PAGE_TOPIC = {
    "page_02": "academic",    # programme_overview
    "page_03": "academic",    # capstone
    "page_04": "admissions",  # admissions requirements
    "page_05": "admissions",  # application information
    "page_06": "financial",   # fees_scholarships
    "page_07": "faq",         # faq
}


def _topic_of(source_table: str, metadata: dict | None) -> str:
    md = metadata or {}
    if source_table in ("admissions_items", "application_status_translations"):
        return "admissions"
    if source_table in ("courses", "course_rules"):
        return "academic"
    if source_table == "career_roles":
        return "career"
    if source_table == "competitor_programs":
        return "comparison"
    if source_table == "knowledge_snippets":
        return "admissions" if md.get("namespace") == "admissions" else "faq"
    if source_table == "programme_pages":
        return _PAGE_TOPIC.get(md.get("page_id"), "faq")
    return "faq"


def _tokenize(text: str) -> list[str]:
    """English/digits by word, Chinese by character (no spaces to split on)."""
    text = text.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9$,.\-]*", text)
    han = re.findall(r"[一-鿿]", text)
    return latin + han


# --- lazy singleton (in-process BM25 index) -----------------------------------

_BM25 = None


# --- retrieval layers ---------------------------------------------------------

def _search_vector(query: str, k: int) -> list[Hit]:
    qvec = embed_text(query)
    rows = vector_search_by_embedding(qvec, k)
    return [
        Hit(chunk_key=r["chunk_key"], source_table=r["source_table"],
            content=r["content"], context=r["context"],
            answer_type=r["answer_type"], conflict_group=r["conflict_group"],
            authoritative=r["authoritative"], score=r["sim"],
            metadata=r["metadata"], from_vector=True,
            topic=_topic_of(r["source_table"], r["metadata"]))
        for r in rows
    ]


def _search_bm25(query: str, k: int) -> list[Hit]:
    global _BM25
    from rank_bm25 import BM25Okapi

    chunks = fetch_all_chunks()
    if _BM25 is None:
        corpus = [_tokenize(f"{c['context'] or ''}\n{c['content']}") for c in chunks]
        _BM25 = BM25Okapi(corpus)

    scores = _BM25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    hits = []
    for i in ranked:
        if scores[i] <= 0:
            continue
        c = chunks[i]
        hits.append(Hit(
            chunk_key=c["chunk_key"], source_table=c["source_table"],
            content=c["content"], context=c["context"],
            answer_type=c["answer_type"], conflict_group=c["conflict_group"],
            authoritative=c["authoritative"], score=float(scores[i]),
            metadata=c["metadata"], from_bm25=True,
            topic=_topic_of(c["source_table"], c["metadata"])))
    return hits


def _fuse_rrf(vector_hits: list[Hit], bm25_hits: list[Hit], k: int) -> list[Hit]:
    v_rank = {h.chunk_key: i for i, h in enumerate(vector_hits)}
    b_rank = {h.chunk_key: i for i, h in enumerate(bm25_hits)}
    by_key = {h.chunk_key: h for h in vector_hits}
    for h in bm25_hits:
        by_key.setdefault(h.chunk_key, h)

    fused = []
    for key, hit in by_key.items():
        score = 0.0
        if key in v_rank:
            score += W_SEMANTIC * (1 / (v_rank[key] + 1))
        if key in b_rank:
            score += W_BM25 * (1 / (b_rank[key] + 1))
        hit.score = score
        hit.from_vector = key in v_rank
        hit.from_bm25 = key in b_rank
        fused.append(hit)

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:k]


def _retrieve_uncached(
    query: str, top_k: int,
    filter_topics: set[str] | None, boost_topics: set[str] | None,
) -> list[Hit]:
    vector_hits = _search_vector(query, RECALL_K)
    bm25_hits = _search_bm25(query, RECALL_K)

    if filter_topics:
        vector_hits = [h for h in vector_hits if h.topic in filter_topics]
        bm25_hits = [h for h in bm25_hits if h.topic in filter_topics]

    fused = _fuse_rrf(vector_hits, bm25_hits, RECALL_K if boost_topics else top_k)

    if boost_topics:
        for h in fused:
            if h.topic in boost_topics:
                h.score *= TOPIC_BOOST_FACTOR
        fused.sort(key=lambda h: h.score, reverse=True)
        fused = fused[:top_k]

    return fused


# --- Redis cache-aside ---------------------------------------------------------

def _cache_key(
    query: str, top_k: int,
    filter_topics: set[str] | None, boost_topics: set[str] | None,
) -> str:
    normalized = query.strip().lower()
    # filter/boost must be part of the key — otherwise two agents with
    # different topic scoping would read each other's cached results.
    scoping = f"f={sorted(filter_topics or [])}|b={sorted(boost_topics or [])}"
    digest = hashlib.sha256(f"{normalized}|{scoping}".encode("utf-8")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest}:{top_k}"


def _cache_get(key: str) -> list[Hit] | None:
    try:
        raw = get_redis_client().get(key)
    except Exception:
        return None
    if not raw:
        return None
    return [Hit(**d) for d in json.loads(raw)]


def _cache_set(key: str, hits: list[Hit]) -> None:
    try:
        payload = json.dumps([asdict(h) for h in hits])
        get_redis_client().set(key, payload, ex=settings.retrieval_cache_ttl_seconds)
    except Exception:
        pass  # cache is a best-effort optimisation, never block on it


# --- public retrieval entry point -----------------------------------------------

def retrieve(
    query: str, top_k: int = 5,
    filter_topics: set[str] | None = None, boost_topics: set[str] | None = None,
) -> list[Hit]:
    """
    Hybrid retrieval (vector + BM25 + RRF) over the knowledge base, with a
    Redis result cache in front. Never raises: any failure (missing keys,
    unreachable database, etc.) is logged and results in an empty list, so
    callers can fall back to a "no information available" response.

    filter_topics: hard-restrict candidates to these topics before fusion
        (use only for topics with no overlap elsewhere in the corpus, e.g.
        "career", "comparison" — a bad guess here loses recall entirely).
    boost_topics: soft-boost matching hits after fusion without excluding
        anything else (safe default for topics whose boundaries aren't clean,
        e.g. "admissions", "academic", "financial", "faq").
    """
    key = _cache_key(query, top_k, filter_topics, boost_topics)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        hits = _retrieve_uncached(query, top_k, filter_topics, boost_topics)
    except Exception as exc:
        print(f"[rag_service] Warning: retrieval failed — {exc}")
        return []

    _cache_set(key, hits)
    return hits


# --- prompt-context and citation formatting --------------------------------------

_NUSMODS_API = re.compile(r"https?://api\.nusmods\.com/v2/[^/]+/modules/([A-Z0-9]+)\.json")

_FALLBACK_SOURCE = {
    "admissions_items": "NUS MSc DFT admissions requirements (official)",
    "course_rules": "Annex A curriculum structure",
    "application_status_translations": "Application status guide (official)",
    "career_roles": "Career pathway mapping — compiled by this project, not official NUS content",
    "knowledge_snippets": "Programme FAQ (official)",
    "programme_pages": "NUS MSc DFT programme website",
    "courses": "NUSMods course catalogue",
    "competitor_programs": "Competitor programme comparison — compiled by this project",
}


def _source_of(hit: Hit) -> str:
    md = hit.metadata if isinstance(hit.metadata, dict) else {}
    url = md.get("source_url")
    if url:
        m = _NUSMODS_API.match(url)
        return f"https://nusmods.com/courses/{m.group(1)}" if m else url
    label = _FALLBACK_SOURCE.get(hit.source_table, hit.source_table)
    if hit.source_table == "course_rules" and md.get("intake"):
        label += f" ({md['intake']} intake)"
    return label


def build_context(hits: list[Hit]) -> str:
    """Tag each chunk [official]/[advisory] and flag which side of a conflict
    governs — mirrors data_process/rag-backend's answer.py::build_context()
    under its "authoritative_wins" conflict mode."""
    conflict_members: dict[str, list[Hit]] = {}
    for h in hits:
        if h.conflict_group:
            conflict_members.setdefault(h.conflict_group, []).append(h)

    blocks = []
    for i, h in enumerate(hits, 1):
        tags = [f"[{h.answer_type}]"]
        if h.conflict_group and len(conflict_members[h.conflict_group]) > 1:
            tags.append(
                "⚠️GOVERNS this topic" if h.authoritative else
                "⚠️SUPERSEDED on this specific point — its other content and "
                "figures remain valid"
            )
        head = f"[SOURCE {i}] {' '.join(tags)}"
        body = f"{h.context}\n{h.content}" if h.context else h.content
        blocks.append(f"{head}\n{body}")
    return "\n\n---\n\n".join(blocks)


def cited_sources(hits: list[Hit]) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []
    for h in hits:
        s = _source_of(h)
        if s not in seen:
            seen.add(s)
            sources.append(s)
    return sources
