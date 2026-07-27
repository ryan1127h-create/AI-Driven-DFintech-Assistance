"""Skill-match threshold calibration (design doc 13 §4.4).

Sweep the skill_threshold against a labelled set (profile -> gold skill ids),
score by mean F1 (eval.metrics.set_prf), pick the most robust best cell. Uses the
active matcher; re-run after a model swap. RuleSkillMatcher ignores the threshold
(deterministic) — calibration is meaningful for the embedding backend.

    python -m eval.skill_calibrate [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common.skill_matcher import get_skill_matcher
from eval.metrics import set_prf

_CASES = Path(__file__).resolve().parent / "cases" / "skill_match.json"
_THRESHOLDS = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]


def load_cases() -> list[dict]:
    return json.loads(_CASES.read_text(encoding="utf-8"))


def _matcher_at(matcher, threshold):
    from common.skill_matcher import EmbeddingSkillMatcher
    if isinstance(matcher, EmbeddingSkillMatcher):
        return EmbeddingSkillMatcher(skill_threshold=threshold)
    return matcher  # rule backend: threshold-independent


def evaluate_threshold(cases: list[dict], threshold: float, matcher=None) -> dict:
    from common.mock_data import get_profile
    matcher = _matcher_at(matcher or get_skill_matcher(), threshold)
    f1s = []
    for c in cases:
        pred = {h.id for h in matcher.infer_user_skills(get_profile(c["profile_ref"]))}
        f1s.append(set_prf(pred, c["gold_skills"])["f1"])
    mean = sum(f1s) / len(f1s) if f1s else 0.0
    return {"threshold": threshold, "f1": round(mean, 4), "n": len(cases)}


def grid_search(cases: list[dict], matcher=None) -> tuple[dict, list[dict]]:
    base = matcher or get_skill_matcher()
    table = [evaluate_threshold(cases, t, matcher=base) for t in _THRESHOLDS]
    best_f1 = max(r["f1"] for r in table)
    top = [r for r in table if r["f1"] == best_f1]
    best = top[len(top) // 2]
    return best, table


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    best, table = grid_search(load_cases())
    if "--json" in argv:
        print(json.dumps({"best": best, "grid": table}, ensure_ascii=False, indent=2))
    else:
        for r in table:
            print(f"  thr={r['threshold']:.2f}  f1={r['f1']:.3f}")
        print(f"\nBEST: skill_threshold={best['threshold']:.2f} f1={best['f1']:.3f} (n={best['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
