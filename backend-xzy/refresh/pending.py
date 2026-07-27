"""Human-review queue for refreshes that aren't auto-published."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_PENDING_DIR = Path(__file__).resolve().parents[1] / "data" / "_pending"


def queue(source_name: str, draft: dict, diff: list[str], anomalies: list[str],
          reasons: list[str], provenance: dict, pending_dir: Path | None = None) -> Path:
    pending_dir = pending_dir or _PENDING_DIR
    pending_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = pending_dir / f"{source_name}.{ts}.json"
    path.write_text(
        json.dumps(
            {
                "source": source_name,
                "status": "pending",
                "created": datetime.now().isoformat(timespec="seconds"),
                "reasons": reasons,
                "anomalies": anomalies,
                "diff": diff,
                "provenance": provenance,
                "draft": draft,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def list_pending(pending_dir: Path | None = None) -> list[dict]:
    pending_dir = pending_dir or _PENDING_DIR
    if not pending_dir.exists():
        return []
    out = []
    for f in sorted(pending_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.get("status") == "pending":
            out.append({"file": str(f), "source": d["source"],
                        "reasons": d.get("reasons", []), "created": d.get("created")})
    return out


def load(pending_file: Path | str) -> dict:
    return json.loads(Path(pending_file).read_text(encoding="utf-8"))


def mark_resolved(pending_file: Path | str, by: str = "reviewer") -> None:
    path = Path(pending_file)
    d = json.loads(path.read_text(encoding="utf-8"))
    d["status"] = "resolved"
    d["resolved_by"] = by
    d["resolved_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
