"""Refresh pipeline: fetch -> summarize -> validate -> anomaly -> decide ->
auto-publish or queue for review. Approving a queued item publishes it.

Publishing reuses the admin audit/versioning facilities; the runtime engine is
untouched and still reads the same JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from admin import audit, schemas

from . import pending, summarize, tiering
from .fetcher import Fetcher
from .sources import RefreshSource, get_source


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _publish(source: RefreshSource, draft: dict, current: dict, admin: str,
             reason: str, audit_log: Path | None, versions_dir: Path | None) -> str | None:
    archive = None
    if source.file_path.exists():
        archive = str(audit.archive_version(source.file_path, versions_dir))
    changes = audit.compute_diff(current, draft) if current else ["(initial load)"]
    _write_json(source.file_path, draft)
    audit.append_audit(
        audit.make_audit_record(source.name, admin, reason, changes, archive,
                                approved=True, action="refresh"),
        audit_log,
    )
    return archive


def run(source_name: str, fetcher: Fetcher | None = None, *, admin: str = "refresh-bot",
        audit_log: Path | None = None, versions_dir: Path | None = None,
        pending_dir: Path | None = None) -> dict:
    source = get_source(source_name)
    fetcher = fetcher or source.default_fetcher

    raw = fetcher.fetch()
    draft = summarize.to_draft(source, raw)
    ok, err = schemas.validate_draft(source.schema, draft)

    is_first = not source.file_path.exists()
    current = {} if is_first else _read_json(source.file_path)
    anomalies = [] if is_first else source.anomaly_fn(current, draft)
    decision = tiering.decide(schema_ok=ok, is_first_load=is_first,
                              trusted=source.trusted, anomalies=anomalies)
    provenance = {"source_url": draft.get("source_url"), "fetched_at": draft.get("fetched_at")}

    if decision.action == "rejected":
        return {"status": "rejected", "error": err}

    diff = ["(initial load)"] if is_first else audit.compute_diff(current, draft)

    if decision.action == "auto_publish":
        if not diff:
            return {"status": "no_change"}
        archive = _publish(source, draft, current, admin, "auto refresh", audit_log, versions_dir)
        return {"status": "auto_published", "changed_fields": diff, "version_archived": archive}

    # needs_review
    pfile = pending.queue(source_name, draft, diff, anomalies, decision.reasons,
                          provenance, pending_dir)
    return {"status": "queued_for_review", "reasons": decision.reasons,
            "anomalies": anomalies, "pending_file": str(pfile)}


def approve_pending(pending_file: Path | str, admin: str = "reviewer", *,
                    audit_log: Path | None = None, versions_dir: Path | None = None) -> dict:
    data = pending.load(pending_file)
    source = get_source(data["source"])
    draft = data["draft"]

    ok, err = schemas.validate_draft(source.schema, draft)
    if not ok:
        return {"status": "rejected", "error": err}

    current = {} if not source.file_path.exists() else _read_json(source.file_path)
    archive = _publish(source, draft, current, admin,
                       f"approved pending {Path(pending_file).name}", audit_log, versions_dir)
    pending.mark_resolved(pending_file, by=admin)
    changes = audit.compute_diff(current, draft) if current else ["(initial load)"]
    return {"status": "approved", "changed_fields": changes, "version_archived": archive}
