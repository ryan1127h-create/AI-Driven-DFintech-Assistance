"""
Hybrid retrieval (vector + BM25 + RRF) against the knowledge base, with a
cache in front, plus the prompt-context and citation formatting used by
every retrieval-grounded answer.

Query-time embedding uses the same model the chunks were embedded with
(OpenAI text-embedding-3-small, 1536 dims) — using a different model here
would put queries and stored vectors in different vector spaces, making
cosine similarity meaningless.

Cohere rerank is intentionally not used here: its evaluated marginal gain
was small and its rate limit does not fit a multi-user backend. Adding it
back later only means adding one more stage to retrieve().
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict

from app.adapters.knowledge_db_adapter import knowledge_db
from app.adapters.openai_embedding_adapter import embedding
from app.adapters.redis_cache_adapter import cache
from app.core.config import settings
from app.core.logging import get_logger
from app.domains.knowledge_retrieval.models import Hit

logger = get_logger(__name__)

# RRF weights: semantic-first, keyword as a booster for codes/numbers that
# embeddings tend to blur together (e.g. FT5005 vs FT5009).
W_SEMANTIC = 0.8
W_BM25 = 0.2

# Each of vector/BM25 first pulls this many candidates for RRF to fuse.
# 50 is generous relative to the corpus size (~160 chunks).
RECALL_K = 50

# Score multiplier applied to hits whose topic is in a caller's
# boost_topics, after RRF fusion. A soft nudge, not a hard filter.
TOPIC_BOOST_FACTOR = 1.3

# course_rules carries two parallel intake cohorts (2025-08-and-earlier /
# 2026-08-onwards, same 6 rule categories each) with nothing in retrieval
# distinguishing them — a query like "core course requirements" competes
# equally between both regardless of which cohort is actually current,
# risking a stale-rules answer for the prospective/current-intake students
# who are the overwhelming majority of callers. course_recommendation's
# policy/curriculum.py keeps the same value in CURRENT_INTAKE (its policy
# layer may not import this domain); test_knowledge_catalog.py checks the
# two agree. Deliberately a soft down-weight (never a filter/
# exclusion) applied to the non-current cohort's course_rules hits — a
# caller that genuinely needs the older cohort's rules can still surface
# them, just ranked lower rather than removed outright.
CURRENT_CURRICULUM_INTAKE = "2026-08-onwards"
INTAKE_MISMATCH_PENALTY = 0.5

_CACHE_KEY_PREFIX = "rag:retrieve:"

# The topic bucket callers filter/boost by. The web chunks (programme
# pages and FAQ answers) carry their own in metadata['topic'], set when they
# are built (scripts/knowledge/rebuild_web_chunks.py); the chunks built from
# the structured tables follow from their table.
_TABLE_TOPIC = {
    "admissions_items": "admissions",
    "application_status_translations": "admissions",
    "courses": "academic",
    "course_rules": "academic",
    "tags_definition": "career",
}


def _topic_of(source_table: str, metadata: dict | None) -> str:
    return (metadata or {}).get("topic") or _TABLE_TOPIC.get(source_table, "faq")


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
    qvec = embedding.embed(query)
    rows = knowledge_db.vector_search_by_embedding(qvec, k)
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

    chunks = knowledge_db.fetch_all_chunks()
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


def _apply_intake_penalty(hits: list[Hit]) -> None:
    """Down-weights (in place) course_rules hits from the non-current
    intake cohort — see INTAKE_MISMATCH_PENALTY above. A no-op for every
    other source_table."""
    for h in hits:
        if h.source_table != "course_rules":
            continue
        intake = (h.metadata or {}).get("intake")
        if intake and intake != CURRENT_CURRICULUM_INTAKE:
            h.score *= INTAKE_MISMATCH_PENALTY


def _retrieve_uncached(
    query: str, top_k: int,
    filter_topics: set[str] | None, boost_topics: set[str] | None,
) -> list[Hit]:
    vector_hits = _search_vector(query, RECALL_K)
    bm25_hits = _search_bm25(query, RECALL_K)

    if filter_topics:
        vector_hits = [h for h in vector_hits if h.topic in filter_topics]
        bm25_hits = [h for h in bm25_hits if h.topic in filter_topics]

    # Always fuse over the full RECALL_K candidate pool first, then apply
    # the intake penalty and any topic boost, then cut to top_k once at the
    # end — this way both adjustments can influence WHICH hits survive the
    # cut, not just their order within an already-final set.
    fused = _fuse_rrf(vector_hits, bm25_hits, RECALL_K)
    _apply_intake_penalty(fused)

    if boost_topics:
        for h in fused:
            if h.topic in boost_topics:
                h.score *= TOPIC_BOOST_FACTOR

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:top_k]


# --- cache-aside ---------------------------------------------------------------

def _cache_key(
    query: str, top_k: int,
    filter_topics: set[str] | None, boost_topics: set[str] | None,
) -> str:
    normalized = query.strip().lower()
    # filter/boost must be part of the key — otherwise two callers with
    # different topic scoping would read each other's cached results.
    scoping = f"f={sorted(filter_topics or [])}|b={sorted(boost_topics or [])}"
    digest = hashlib.sha256(f"{normalized}|{scoping}".encode("utf-8")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest}:{top_k}"


def _cache_get(key: str) -> list[Hit] | None:
    try:
        raw = cache.get(key)
    except Exception:
        return None
    if not raw:
        return None
    return [Hit(**d) for d in json.loads(raw)]


def _cache_set(key: str, hits: list[Hit]) -> None:
    try:
        payload = json.dumps([asdict(h) for h in hits])
        cache.set(key, payload, ttl_seconds=settings.retrieval_cache_ttl_seconds)
    except Exception:
        pass  # cache is a best-effort optimisation, never block on it


# --- public retrieval entry point -----------------------------------------------

def retrieve(
    query: str, top_k: int = 5,
    filter_topics: set[str] | None = None, boost_topics: set[str] | None = None,
) -> list[Hit]:
    """
    Hybrid retrieval (vector + BM25 + RRF) over the knowledge base, with a
    cache in front. Never raises: any failure (missing keys, unreachable
    database, etc.) is logged and results in an empty list, so callers can
    fall back to a "no information available" response.

    filter_topics: hard-restrict candidates to these topics before fusion
        (use only for topics with no overlap elsewhere in the corpus, e.g.
        "career" — a bad guess here loses recall entirely).
    boost_topics: soft-boost matching hits after fusion without excluding
        anything else (safe default for topics whose boundaries aren't
        clean, e.g. "admissions", "academic", "financial", "faq").
    """
    key = _cache_key(query, top_k, filter_topics, boost_topics)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        hits = _retrieve_uncached(query, top_k, filter_topics, boost_topics)
    except Exception:
        logger.exception("knowledge retrieval failed")
        return []

    _cache_set(key, hits)
    return hits


# --- prompt-context and citation formatting --------------------------------------

_NUSMODS_API = re.compile(r"https?://api\.nusmods\.com/v2/[^/]+/modules/([A-Z0-9]+)\.json")

_FALLBACK_SOURCE = {
    "admissions_items": "NUS MSc DFT admissions requirements (official)",
    "course_rules": "Annex A curriculum structure",
    "application_status_translations": "Application status guide (official)",
    "tags_definition": "Role tags — compiled by this project, not official NUS content",
    "programme_pages": "NUS MSc DFT programme website",
    "courses": "NUSMods course catalogue",
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
    """Tags each chunk [official]/[advisory] and flags which side of a
    conflict governs, under an "authoritative_wins" conflict-resolution
    mode."""
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


# --- structured, non-search access ------------------------------------------
#
# The three functions below are deterministic reads, not retrieval — for a
# caller that needs "every row of X", not "the most relevant chunks for this
# query". course_recommendation's chat adapter (see
# app/tools/specialist/course_recommendation/s2_assembly/) is the current
# consumer of all three.

# course_requirements.prerequisite keeps corequisites in the same text, as
# " | "-separated parts prefixed "Corequisite:" (there is no corequisite
# column). _split_requirements() moves them into corequisite_grad_text. The
# importer's older "并修(coreq):" prefix is still read.
_COREQ_PREFIX = re.compile(r"^\s*(?:并修\s*)?\(?\s*coreq(?:uisite)?\s*\)?\s*[:：]\s*", re.IGNORECASE)


def _split_requirements(text: str | None) -> tuple[str | None, str | None]:
    """(prerequisite, corequisite) from the stored prerequisite text."""
    prereqs, coreqs = [], []
    for part in (text or "").split("|"):
        part = part.strip()
        if not part:
            continue
        match = _COREQ_PREFIX.match(part)
        if match:
            coreqs.append(part[match.end():].strip())
        else:
            prereqs.append(part)
    return " | ".join(prereqs) or None, "; ".join(coreqs) or None


def reload_catalogue() -> None:
    """Drops what this process has cached from the knowledge schema after
    the staff console edits it: the tables and chunks (re-read on next use,
    which also rebuilds the BM25 index) and the cached retrievals, which
    may quote the old text."""
    knowledge_db.invalidate()
    try:
        cache.delete_prefix(_CACHE_KEY_PREFIX)
    except Exception as exc:  # best effort: cached retrievals expire on their own
        logger.warning("could not clear the cached retrievals: %s", exc)


def embed_for_retrieval(text: str) -> list[float]:
    """Embeds text with the same model the retriever embeds queries with,
    so a rebuilt chunk stays comparable to every other chunk."""
    return embedding.embed(text)


def warm_cache() -> None:
    """Loads the cached catalogue tables (courses, chunks, course tags,
    role tags, electives) so the first request in a process doesn't pay
    for them. Safe to call more than once."""
    list_courses()
    list_curriculum_rules()
    list_course_tags()
    list_role_tags()
    list_course_electives()
    list_course_schedule()


def list_courses() -> list[dict]:
    """The complete course catalogue, unranked — one dict per course
    assembled from the course tables (see
    knowledge_db_adapter.fetch_all_courses()); workload as floats, and
    corequisites split out of the prerequisite text."""
    courses = []
    for row in knowledge_db.fetch_all_courses():
        prerequisite, corequisite = _split_requirements(row["prerequisite_grad_text"])
        courses.append({
            **row,
            "prerequisite_grad_text": prerequisite,
            "corequisite_grad_text": corequisite,
            "workload": [float(x) for x in row["workload"]] if row["workload"] is not None else None,
        })
    return courses


def list_curriculum_rules() -> list[dict]:
    """Every course_rules chunk for the current intake (CURRENT_CURRICULUM_INTAKE),
    verbatim — a deterministic filter over fetch_all_chunks(), not a
    semantic search, so nothing is missed or reordered by relevance
    scoring."""
    return [
        c for c in knowledge_db.fetch_all_chunks()
        if c["source_table"] == "course_rules"
        and (c["metadata"] or {}).get("intake") == CURRENT_CURRICULUM_INTAKE
    ]


def _clock(hhmm: str) -> str:
    """'1830' -> '18:30'."""
    return f"{hhmm[:2]}:{hhmm[2:]}" if len(hhmm) == 4 else hhmm


def list_course_schedule() -> dict[str, list[dict]]:
    """Every course's class slots for the regular semesters on file,
    grouped by course code: {ay, semester (int), lesson_type, class_no,
    day, start, end} with times as "HH:MM". A lesson type with several
    class numbers offers a choice of slot; one with a single number is
    fixed."""
    grouped: dict[str, list[dict]] = {}
    for row in knowledge_db.fetch_course_schedule():
        grouped.setdefault(row["course_code"], []).append({
            "ay": row["ay"],
            "semester": int(row["semester"]),
            "lesson_type": row["lesson_type"],
            "class_no": row["class_no"],
            "day": row["day"],
            "start": _clock(row["start_time"]),
            "end": _clock(row["end_time"]),
        })
    return grouped


def list_course_electives() -> dict[str, list[str]]:
    """Every course's elective-vertical membership(s), grouped by course
    code. A course can belong to more than one entry here (or to none,
    e.g. a pure core course) — this is where a core-replacement course
    that's also a vertical elective (see contracts.py's dual-membership
    note) shows both memberships, unlike the single-valued
    `annex_section` column list_courses() returns."""
    grouped: dict[str, list[str]] = {}
    for row in knowledge_db.fetch_course_electives():
        grouped.setdefault(row["course_code"], []).append(row["vertical"])
    return grouped


def list_role_tags() -> list[dict]:
    """The 12 role tags (role families): {tag, name_en, name_zh,
    definition, required_skills}. Courses carry these tags, and a profile's
    target_role_families takes its values from them."""
    return [
        {**row, "required_skills": list(row["required_skills"] or [])}
        for row in knowledge_db.fetch_role_tags()
    ]


def list_course_tags() -> dict[str, list[str]]:
    """Every course's role tags, grouped by course code."""
    grouped: dict[str, list[str]] = {}
    for row in knowledge_db.fetch_course_tags():
        grouped.setdefault(row["course_code"], []).append(row["tag"])
    return grouped


def list_admissions_items() -> dict[str, dict]:
    """key -> {label, description, required} for every admissions document."""
    return {
        row["key"]: {"label": row["label"], "description": row["why"], "required": bool(row["required"])}
        for row in knowledge_db.fetch_admissions_items()
    }


def explain_application_status(status_code: str | None) -> dict:
    """{status_label, next_step} for an application status code (both None
    when the code has no explanation)."""
    for row in knowledge_db.fetch_status_translations():
        if row["status_code"] == status_code:
            return {"status_label": row["human_status"], "next_step": row["next_step"]}
    return {"status_label": None, "next_step": None}


def get_role_profile(tag: str) -> dict | None:
    """{role_id, role_title, required_skills} for one role tag (role_id is
    the tag, role_title its English name), or None for an unknown tag."""
    for row in list_role_tags():
        if row["tag"] == tag:
            return {"role_id": row["tag"], "role_title": row["name_en"], "required_skills": row["required_skills"]}
    return None


def _normalize_role_text(text: str) -> str:
    text = text.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def match_role_tag(text: str) -> str | None:
    """Maps free text naming a role family ("machine learning & AI",
    "data_analytics", "I want a blockchain job") to its tag — the tag key
    or English name appearing in the text, preferring the longest match.
    None if no tag is named."""
    normalized = f" {_normalize_role_text(text)} "
    best, best_len = None, 0
    for row in list_role_tags():
        for name in (row["tag"], row["name_en"]):
            candidate = _normalize_role_text(name)
            if candidate and f" {candidate} " in normalized and len(candidate) > best_len:
                best, best_len = row["tag"], len(candidate)
    return best
