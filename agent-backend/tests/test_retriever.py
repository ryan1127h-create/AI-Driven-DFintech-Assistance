"""Tests for common.retriever — local retrieval backends."""
from __future__ import annotations

import pytest
from common import config
from common.confidence import RetrievalChunk
from common.retriever import BM25Retriever


def _bm25() -> BM25Retriever:
    return BM25Retriever()


def test_returns_retrieval_chunks_with_source_id():
    out = _bm25().retrieve("IELTS English language requirement", "admissions", top_k=3)
    assert out and all(isinstance(c, RetrievalChunk) for c in out)
    assert out[0].source_id is not None


def test_english_query_ranks_english_chunk_first():
    out = _bm25().retrieve("Do I need IELTS or TOEFL for English proficiency?",
                           "admissions", top_k=3)
    assert out[0].source_id == "admissions_rules#english_proficiency"


def test_namespace_filter_excludes_other_namespaces():
    out = _bm25().retrieve("blockchain payments", "curriculum", top_k=5)
    assert out
    assert all(c.source_id.startswith("module_catalog#") for c in out)


def test_empty_query_returns_empty():
    assert _bm25().retrieve("", "admissions") == []


def test_scores_are_normalised_0_1():
    out = _bm25().retrieve("blockchain", "curriculum", top_k=5)
    assert all(0.0 <= c.score <= 1.0 for c in out)


def test_factory_returns_bm25_when_no_key(monkeypatch):
    from common import config, retriever
    monkeypatch.setattr(config, "is_configured", lambda: False)
    r = retriever.get_retriever()
    assert isinstance(r, retriever.BM25Retriever)


def test_embedding_retriever_ranks_by_cosine(monkeypatch, tmp_path):
    """With a stub embedder, the chunk closest in vector space ranks first.
    Deterministic: no network, fixed vectors."""
    from common import retriever as R

    def fake_embed(texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "ielts" in tl or "english" in tl:
                out.append([1.0, 0.0])
            elif "blockchain" in tl:
                out.append([0.0, 1.0])
            else:
                out.append([0.5, 0.5])
        return out

    monkeypatch.setattr(R, "_cache_path", lambda: tmp_path / "_emb.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)

    er = R.EmbeddingRetriever()
    out = er.retrieve("english language IELTS requirement", "admissions", top_k=1)
    assert out and out[0].source_id == "admissions_rules#english_proficiency"


def test_embedding_cache_rebuilds_on_model_fingerprint_change(monkeypatch, tmp_path):
    from common import retriever as R

    calls = {"n": 0}

    def fake_embed(texts):
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(R, "_cache_path", lambda: tmp_path / "_emb.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-A")
    R.EmbeddingRetriever()  # builds cache for model-A
    n_after_a = calls["n"]
    R.EmbeddingRetriever()  # same model -> reuse cache, no new embed calls
    assert calls["n"] == n_after_a
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-B")
    R.EmbeddingRetriever()  # different model -> rebuild
    assert calls["n"] > n_after_a


@pytest.mark.skipif(not config.is_configured(),
                    reason="needs DeepSeek/embedding key for live call")
def test_live_embedding_retriever_smoke():
    from common.retriever import EmbeddingRetriever

    try:
        er = EmbeddingRetriever()
        out = er.retrieve("English language proof", "admissions", top_k=2)
    except Exception as e:  # a configured key doesn't guarantee a working endpoint
        pytest.skip(f"embedding endpoint unavailable: {e}")
    assert out
    assert all(0.0 <= c.score <= 1.0 for c in out)
