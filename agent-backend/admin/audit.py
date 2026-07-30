"""Versioning, diffing, and audit logging for the authoring pipeline."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_VERSIONS_DIR = _DATA_DIR / "_versions"
_AUDIT_LOG = _DATA_DIR / "_audit_log.jsonl"


def compute_diff(old: dict, new: dict, prefix: str = "") -> list[str]:
    """Return dotted field paths that changed between two nested dicts.

    Reports added / removed / modified leaf paths. Order-independent.
    """
    changes: list[str] = []
    keys = set(old) | set(new)
    for key in sorted(keys, key=str):
        path = f"{prefix}.{key}" if prefix else str(key)
        in_old, in_new = key in old, key in new
        if in_old and not in_new:
            changes.append(f"{path} (removed)")
        elif in_new and not in_old:
            changes.append(f"{path} (added)")
        else:
            ov, nv = old[key], new[key]
            if isinstance(ov, dict) and isinstance(nv, dict):
                changes.extend(compute_diff(ov, nv, path))
            elif ov != nv:
                changes.append(path)
    return changes


def archive_version(file_path: Path, versions_dir: Path | None = None) -> Path:
    """Copy the current file to a timestamped archive. Returns archive path."""
    versions_dir = versions_dir or _VERSIONS_DIR
    versions_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = versions_dir / f"{file_path.stem}.{ts}.json"
    shutil.copy2(file_path, archive)
    return archive


def append_audit(record: dict, audit_log: Path | None = None) -> None:
    """Append one JSON record as a line to the append-only audit log."""
    audit_log = audit_log or _AUDIT_LOG
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_audit_log(audit_log: Path | None = None, limit: int = 100) -> list[dict]:
    """Return audit records, most recent first (up to `limit`)."""
    audit_log = audit_log or _AUDIT_LOG
    if not audit_log.exists():
        return []
    records = []
    for line in audit_log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(records))[:limit]


def list_versions(file_stem: str, versions_dir: Path | None = None) -> list[dict]:
    """List archived versions for a file stem, most recent first.

    Returns dicts: {name, path, timestamp}.
    """
    versions_dir = versions_dir or _VERSIONS_DIR
    if not versions_dir.exists():
        return []
    out = []
    for p in versions_dir.glob(f"{file_stem}.*.json"):
        out.append({"name": p.name, "path": str(p), "timestamp": p.stem.split(".", 1)[-1]})
    return sorted(out, key=lambda d: d["timestamp"], reverse=True)


def make_audit_record(
    target: str,
    admin: str,
    instruction: str,
    changed_fields: list[str],
    version_archived: str | None,
    approved: bool,
    action: str = "edit",
) -> dict:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,  # "edit" | "rollback"
        "target": target,
        "admin": admin,
        "instruction": instruction,
        "changed_fields": changed_fields,
        "version_archived": version_archived,
        "approved": approved,
    }
