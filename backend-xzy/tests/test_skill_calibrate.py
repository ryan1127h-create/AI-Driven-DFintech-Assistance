"""Tests for eval.skill_calibrate — threshold sweep for skill matching."""
from __future__ import annotations

from eval.skill_calibrate import load_cases, evaluate_threshold, grid_search


def test_cases_load():
    cs = load_cases()
    assert len(cs) >= 4
    assert all("gold_skills" in c for c in cs)


def test_evaluate_threshold_returns_f1():
    cs = load_cases()
    from common.skill_matcher import RuleSkillMatcher
    r = evaluate_threshold(cs, 0.5, matcher=RuleSkillMatcher())
    assert 0.0 <= r["f1"] <= 1.0
    assert r["threshold"] == 0.5


def test_grid_search_picks_best_f1():
    cs = load_cases()
    from common.skill_matcher import RuleSkillMatcher
    best, table = grid_search(cs, matcher=RuleSkillMatcher())
    assert best in table
    assert best["f1"] == max(r["f1"] for r in table)
