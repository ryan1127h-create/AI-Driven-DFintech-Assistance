"""Threshold calibration for the confidence gate (design doc 12 §4).

Grid-search the decide() thresholds against a labelled query set, score by
decision accuracy, and report the best cell. Provider-agnostic: uses the active
retriever (BM25 offline, embedding when configured), so re-running after a model
swap yields fresh thresholds.

    python -m eval.calibrate            # human-readable
    python -m eval.calibrate --json     # machine-readable
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common.confidence import decide
from common.retriever import get_retriever

_QUERIES = Path(__file__).resolve().parent / "cases" / "retrieval_queries.json"

# Candidate threshold values to scan — wide enough for BOTH backends: lexical/BM25
# (answer ~0.7-1.0, escalate ~0.1-0.2) and embedding cosine, whose distribution is
# denser/higher (answer ~0.65-0.87, escalate ~0.4-0.69).
_LOWS = [0.20, 0.35, 0.50]
_CLARS = [0.35, 0.50, 0.65]
_STRICTS = [0.45, 0.55, 0.65, 0.70, 0.75]


def load_queries() -> list[dict]:
    return json.loads(_QUERIES.read_text(encoding="utf-8"))


def _prefetch(queries: list[dict], retriever) -> list[tuple[dict, list[dict]]]:
    """Retrieve each query ONCE (scores don't depend on thresholds). Avoids
    re-embedding the same query for every grid cell."""
    out: list[tuple[dict, list[dict]]] = []
    for q in queries:
        chunks = retriever.retrieve(q["query"], q.get("namespace"))
        payload = [{"text": c.text, "source_id": c.source_id, "score": c.score}
                   for c in chunks]
        out.append((q, payload))
    return out


def _score_grid(prefetched: list[tuple[dict, list[dict]]],
                low: float, clar: float, strict: float) -> dict:
    correct = 0
    for q, payload in prefetched:
        decision = decide(q["query"], payload, answer_type="official",
                          high_risk=False, low_threshold=low,
                          clarification_threshold=clar, strict_threshold=strict)
        if decision.action == q["gold_action"]:
            correct += 1
    n = len(prefetched)
    return {"low": low, "clarification": clar, "strict": strict,
            "accuracy": correct / n if n else 0.0, "n": n}


def evaluate_thresholds(queries: list[dict], low: float, clarification: float,
                        strict: float, retriever=None) -> dict:
    retriever = retriever or get_retriever()
    return _score_grid(_prefetch(queries, retriever), low, clarification, strict)


def grid_search(queries: list[dict], retriever=None) -> tuple[dict, list[dict]]:
    retriever = retriever or get_retriever()
    prefetched = _prefetch(queries, retriever)  # retrieve once, reuse per cell
    table: list[dict] = []
    for low in _LOWS:
        for clar in _CLARS:
            if clar < low:
                continue
            for strict in _STRICTS:
                table.append(_score_grid(prefetched, low, clar, strict))
    # Among the highest-accuracy cells, prefer the median-strict one: it sits in
    # the middle of the separable region, maximising margin from both the answer
    # and escalate score clusters (more robust than the first/edge cell).
    best_acc = max(r["accuracy"] for r in table)
    top = sorted((r for r in table if r["accuracy"] == best_acc),
                 key=lambda r: (r["strict"], r["low"], r["clarification"]))
    best = top[len(top) // 2]
    return best, table


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    queries = load_queries()
    best, table = grid_search(queries)
    if "--json" in argv:
        print(json.dumps({"best": best, "grid": table}, ensure_ascii=False, indent=2))
    else:
        print("=== Threshold calibration (active retriever) ===\n")
        for row in sorted(table, key=lambda r: r["accuracy"], reverse=True)[:10]:
            print(f"  acc={row['accuracy']:.3f}  low={row['low']:.2f} "
                  f"clar={row['clarification']:.2f} strict={row['strict']:.2f}")
        print(f"\nBEST: low={best['low']:.2f} clarification={best['clarification']:.2f} "
              f"strict={best['strict']:.2f}  accuracy={best['accuracy']:.3f} "
              f"(n={best['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
