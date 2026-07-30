"""Evaluation runner: labelled cases -> rule engine -> scorecard.

Evaluates the *deterministic* engine layer (not the LLM narration), so results
are reproducible and offline. Run as a module:

    python -m eval.runner          # human-readable scorecard
    python -m eval.runner --json   # machine-readable (regression/diff)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.agents.checklist.engine import build_checklist
from app.agents.navigator.engine import guide_for_role
from common.mock_data import get_profile
from common.profile import TargetRole, UserProfile
from eval.metrics import set_prf

_CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass
class CaseResult:
    id: str
    agent: str
    metrics: dict[str, float]
    passed: bool
    details: list[str] = field(default_factory=list)


def _resolve_profile(case: dict) -> UserProfile:
    if case.get("profile_ref") is not None:
        return get_profile(str(case["profile_ref"]))
    if case.get("profile_inline") is not None:
        return UserProfile(**case["profile_inline"])
    raise ValueError(f"case {case.get('id')!r} has no profile_ref or profile_inline")


def _eval_checklist(case: dict, profile: UserProfile) -> CaseResult:
    expect = case.get("expect", {})
    today = date.fromisoformat(case["today"]) if case.get("today") else None
    result = build_checklist(profile, today=today)

    present = {it.key for it in result.items}
    status_by_key = {it.key: it.status for it in result.items}
    details: list[str] = []
    metrics: dict[str, float] = {}

    must_include = expect.get("must_include")
    if must_include is not None:
        hit = present & set(must_include)
        metrics["include_recall"] = set_prf(present, must_include)["recall"]
        for k in must_include:
            if k not in present:
                details.append(f"missing required item: {k}")

    must_exclude = expect.get("must_exclude")
    if must_exclude is not None:
        violations = [k for k in must_exclude if k in present]
        metrics["exclude_ok"] = 0.0 if violations else 1.0
        for k in violations:
            details.append(f"item should be excluded but present: {k}")

    want_status = expect.get("status")
    if want_status is not None:
        correct = 0
        for k, want in want_status.items():
            got = status_by_key.get(k)
            if got == want:
                correct += 1
            else:
                details.append(f"status[{k}]: got {got!r}, want {want!r}")
        metrics["status_accuracy"] = correct / len(want_status) if want_status else 1.0

    return CaseResult(case["id"], "checklist", metrics, not details, details)


def _eval_navigator(case: dict, profile: UserProfile) -> CaseResult:
    expect = case.get("expect", {})
    role = TargetRole(case["role"])
    from common.skill_matcher import RuleSkillMatcher
    # B scorecard is a deterministic baseline -> always the rule backend,
    # independent of whether an embedding backend is configured.
    g = guide_for_role(profile, role, matcher=RuleSkillMatcher())

    predicted = set(g.skill_gaps)
    expected = set(expect.get("skill_gaps", []))
    prf = set_prf(predicted, expected)
    details: list[str] = []
    if predicted != expected:
        details.append(
            f"skill_gaps: got {sorted(predicted)}, want {sorted(expected)}"
        )
    metrics = {"gap_f1": prf["f1"], "gap_precision": prf["precision"],
               "gap_recall": prf["recall"]}
    return CaseResult(case["id"], "navigator", metrics, not details, details)


_EVALUATORS = {"checklist": _eval_checklist, "navigator": _eval_navigator}


def evaluate_case(case: dict) -> CaseResult:
    agent = case.get("agent")
    evaluator = _EVALUATORS.get(agent)
    if evaluator is None:
        raise ValueError(f"unknown agent {agent!r} in case {case.get('id')!r}")
    return evaluator(case, _resolve_profile(case))


def load_cases(cases_dir: Path = _CASES_DIR) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(cases_dir.glob("*.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        # Skip files that don't contain agent-eval records (e.g. retrieval query sets).
        cases.extend(r for r in records if "agent" in r)
    return cases


def run(cases_dir: Path = _CASES_DIR) -> list[CaseResult]:
    return [evaluate_case(c) for c in load_cases(cases_dir)]


def _print_scorecard(results: list[CaseResult]) -> None:
    by_agent: dict[str, list[CaseResult]] = {}
    for r in results:
        by_agent.setdefault(r.agent, []).append(r)

    print("=== Evaluation scorecard (deterministic engine layer) ===\n")
    total_pass = 0
    for agent, rs in sorted(by_agent.items()):
        passed = sum(1 for r in rs if r.passed)
        total_pass += passed
        print(f"## {agent}: {passed}/{len(rs)} cases passed")
        agg: dict[str, list[float]] = {}
        for r in rs:
            mark = "PASS" if r.passed else "FAIL"
            print(f"  [{mark}] {r.id}  " + ", ".join(
                f"{k}={v:.2f}" for k, v in r.metrics.items()))
            for k, v in r.metrics.items():
                agg.setdefault(k, []).append(v)
            for d in r.details:
                print(f"         - {d}")
        if agg:
            means = ", ".join(f"{k}={sum(v) / len(v):.3f}" for k, v in agg.items())
            print(f"  mean: {means}")
        print()
    print(f"TOTAL: {total_pass}/{len(results)} cases passed")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    results = run()
    if "--json" in argv:
        payload = [
            {"id": r.id, "agent": r.agent, "passed": r.passed,
             "metrics": r.metrics, "details": r.details}
            for r in results
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_scorecard(results)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
