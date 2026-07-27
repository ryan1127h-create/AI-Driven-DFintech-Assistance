"""Set-based quality metrics for the evaluation scorecard.

Pure functions, stdlib-only. ``set_prf`` compares a predicted set against a
gold/expected set and returns precision, recall and F1.

Conventions for empty sets:
- expected empty  -> recall = 1.0 (nothing was required, nothing missed)
- predicted empty -> precision = 1.0 (nothing was claimed, nothing wrong)
- both empty      -> perfect (1/1/1): correctly predicting "nothing here"
"""
from __future__ import annotations

from typing import Iterable


def set_prf(predicted: Iterable, expected: Iterable) -> dict[str, float]:
    """Return {"precision", "recall", "f1"} comparing predicted vs expected."""
    pred = set(predicted)
    exp = set(expected)
    overlap = len(pred & exp)

    precision = 1.0 if not pred else overlap / len(pred)
    recall = 1.0 if not exp else overlap / len(exp)
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    return {"precision": precision, "recall": recall, "f1": f1}
