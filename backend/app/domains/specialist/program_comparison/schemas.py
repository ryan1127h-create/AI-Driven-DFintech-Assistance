"""The domain's response: the comparison result as plain JSON data (dates
as ISO strings), with the workflow's diagnostics and stage results."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date

from app.domains.specialist.program_comparison.models import ComparisonResult


def _plain(value):
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def response_from_result(result: ComparisonResult) -> dict:
    degraded = any(s.status == "degraded" for s in result.stage_results)
    return {
        "request_id": result.request_id,
        "mode": result.mode,
        "today": result.today.isoformat(),
        "dimensions": list(result.dimensions),
        "baseline": _plain(result.baseline),
        "subjects": _plain(result.subjects),
        "matches": _plain(result.matches),
        "contrasts": _plain(result.contrasts),
        "personalised": result.personalised,
        "unsupported_factors": list(result.unsupported_factors),
        "goal_check": _plain(result.goal_check),
        "notes": list(result.notes),
        "workflow_status": "degraded" if degraded else "success",
        "diagnostics": [
            {"stage": d.stage, "code": d.code, "message": d.message, "retryable": d.retryable}
            for d in result.diagnostics
        ],
        "stage_results": [s.response_content(i) for i, s in enumerate(result.stage_results, start=1)],
    }
