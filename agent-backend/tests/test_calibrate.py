"""Tests for eval.calibrate — threshold grid search over labelled queries."""
from __future__ import annotations

from eval.calibrate import evaluate_thresholds, grid_search, load_queries


def test_queries_load():
    qs = load_queries()
    assert len(qs) >= 8
    assert {q["gold_action"] for q in qs} <= {"answer", "clarify", "escalate"}


def test_evaluate_thresholds_returns_accuracy():
    qs = load_queries()
    r = evaluate_thresholds(qs, low=0.60, clarification=0.72, strict=0.80)
    assert 0.0 <= r["accuracy"] <= 1.0
    assert r["n"] == len(qs)


def test_grid_search_picks_best_by_accuracy():
    qs = load_queries()
    best, table = grid_search(qs)
    assert table
    assert best in table
    assert best["accuracy"] == max(row["accuracy"] for row in table)
