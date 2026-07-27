"""Tests for common.knowledge — loading curated knowledge chunks."""
from __future__ import annotations

from common.knowledge import KnowledgeChunk, load_knowledge


def test_load_all_returns_chunks():
    chunks = load_knowledge()
    assert len(chunks) >= 15
    assert all(isinstance(c, KnowledgeChunk) for c in chunks)


def test_namespaces_present():
    ns = {c.namespace for c in load_knowledge()}
    assert ns == {"admissions", "curriculum", "faq"}


def test_namespace_filter():
    adm = load_knowledge("admissions")
    assert adm
    assert all(c.namespace == "admissions" for c in adm)


def test_chunk_fields_populated():
    c = next(c for c in load_knowledge("admissions") if c.id == "adm_english")
    assert "IELTS" in c.text or "English" in c.text
    assert c.source_id == "admissions_rules#english_proficiency"
    assert c.source_type == "official"
