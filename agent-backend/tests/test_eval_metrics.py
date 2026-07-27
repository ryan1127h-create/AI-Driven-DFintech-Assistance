"""Tests for eval.metrics — set-based precision/recall/F1 used by the scorecard."""
from __future__ import annotations

from eval.metrics import set_prf


def test_perfect_match_scores_one():
    r = set_prf({"a", "b"}, {"a", "b"})
    assert r == {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_both_empty_is_perfect():
    # Correctly predicting "nothing should be here" is a perfect result.
    r = set_prf(set(), set())
    assert r == {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_missing_one_lowers_recall_only():
    # predicted {a}, expected {a, b}: precision 1.0, recall 0.5
    r = set_prf({"a"}, {"a", "b"})
    assert r["precision"] == 1.0
    assert r["recall"] == 0.5
    assert round(r["f1"], 4) == round(2 / 3, 4)


def test_extra_one_lowers_precision_only():
    # predicted {a, b}, expected {a}: precision 0.5, recall 1.0
    r = set_prf({"a", "b"}, {"a"})
    assert r["precision"] == 0.5
    assert r["recall"] == 1.0
    assert round(r["f1"], 4) == round(2 / 3, 4)


def test_predicted_empty_expected_nonempty_zero_recall():
    r = set_prf(set(), {"a"})
    assert r == {"precision": 1.0, "recall": 0.0, "f1": 0.0}


def test_predicted_nonempty_expected_empty_zero_precision():
    r = set_prf({"a"}, set())
    assert r == {"precision": 0.0, "recall": 1.0, "f1": 0.0}


def test_no_overlap_all_zero():
    r = set_prf({"x"}, {"y"})
    assert r == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_accepts_lists_not_just_sets():
    r = set_prf(["a", "a", "b"], ["a", "b"])
    assert r == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
