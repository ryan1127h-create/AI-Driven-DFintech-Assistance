"""Regression guard: the bundled eval cases must all pass against the current
engines. A failure here means either an engine regression or a stale gold label.
"""
from __future__ import annotations

from eval.runner import load_cases, run


def test_cases_load():
    cases = load_cases()
    assert len(cases) >= 10
    assert {c["agent"] for c in cases} == {"checklist", "navigator"}


def test_all_bundled_cases_pass():
    results = run()
    failures = [(r.id, r.details) for r in results if not r.passed]
    assert not failures, f"eval cases regressed: {failures}"
