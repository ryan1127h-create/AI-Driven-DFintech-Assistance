"""decide() reads PER-BACKEND thresholds from data/thresholds.json, falling back
to built-in constants. Backends: bm25 (offline lexical) and embedding (cosine),
whose calibrated score distributions differ, so each gets its own thresholds."""
from __future__ import annotations

import json

from common import confidence


def _pin(monkeypatch, tmp_path, payload):
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(confidence, "_THRESHOLDS_PATH", f)
    confidence._load_thresholds.cache_clear()


def test_loads_backend_section(tmp_path, monkeypatch):
    _pin(monkeypatch, tmp_path, {
        "bm25": {"low": 0.20, "clarification": 0.35, "strict": 0.65},
        "embedding": {"low": 0.35, "clarification": 0.50, "strict": 0.70},
    })
    assert confidence._load_thresholds("bm25") == {
        "low": 0.20, "clarification": 0.35, "strict": 0.65}
    assert confidence._load_thresholds("embedding") == {
        "low": 0.35, "clarification": 0.50, "strict": 0.70}


def test_unknown_backend_falls_back_to_constants(tmp_path, monkeypatch):
    _pin(monkeypatch, tmp_path, {
        "bm25": {"low": 0.20, "clarification": 0.35, "strict": 0.65}})
    t = confidence._load_thresholds("nonexistent")
    assert t["low"] == confidence.LOW_CONFIDENCE_THRESHOLD
    assert t["clarification"] == confidence.CLARIFICATION_THRESHOLD
    assert t["strict"] == confidence.STRICT_OFFICIAL_THRESHOLD


def test_legacy_flat_file_still_works(tmp_path, monkeypatch):
    # Backward compat: a flat {low,clarification,strict} file applies to any backend.
    _pin(monkeypatch, tmp_path, {"low": 0.42, "clarification": 0.55, "strict": 0.88})
    assert confidence._load_thresholds("bm25") == {
        "low": 0.42, "clarification": 0.55, "strict": 0.88}


def test_falls_back_to_constants_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(confidence, "_THRESHOLDS_PATH", tmp_path / "nope.json")
    confidence._load_thresholds.cache_clear()
    t = confidence._load_thresholds("bm25")
    assert t["low"] == confidence.LOW_CONFIDENCE_THRESHOLD
    assert t["strict"] == confidence.STRICT_OFFICIAL_THRESHOLD


def test_decide_picks_thresholds_by_backend(tmp_path, monkeypatch):
    _pin(monkeypatch, tmp_path, {
        "bm25": {"low": 0.20, "clarification": 0.35, "strict": 0.55},
        "embedding": {"low": 0.35, "clarification": 0.50, "strict": 0.70},
    })
    # Same official-source chunk at similarity 0.68, judged under two backends.
    chunks = [{"text": "x", "source_id": "s#1", "score": 0.68}]
    d_bm = confidence.decide("q", chunks, answer_type="official",
                             high_risk=True, backend="bm25")
    assert d_bm.action == "answer"        # 0.68 >= bm25 strict 0.55
    d_em = confidence.decide("q", chunks, answer_type="official",
                             high_risk=True, backend="embedding")
    assert d_em.action == "escalate"      # 0.68 < embedding strict 0.70
