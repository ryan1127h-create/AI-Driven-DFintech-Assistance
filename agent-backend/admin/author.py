"""CLI authoring tool + testable core.

apply_draft() does everything except the LLM call (validate -> diff -> approve
-> archive -> write -> audit), so it can be unit-tested without DeepSeek.
main() wraps it: it calls extract() for the LLM step, then apply_draft().
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from . import audit, schemas
from .registry import EditableTarget, all_target_names, get_target


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def apply_draft(
    target: EditableTarget,
    draft: dict,
    instruction: str,
    admin: str,
    approver: Callable[[list[str]], bool],
    *,
    audit_log: Path | None = None,
    versions_dir: Path | None = None,
) -> dict:
    """Validate -> diff -> approve -> archive -> write -> audit.

    Returns a result dict describing what happened. No LLM here. The file is
    written ONLY if validation passes AND the approver returns True.
    """
    ok, err = schemas.validate_draft(target.schema, draft)
    if not ok:
        return {"status": "rejected", "reason": "validation_failed", "error": err}

    current = _read_json(target.file_path)
    changes = audit.compute_diff(current, draft)
    if not changes:
        return {"status": "no_change", "changed_fields": []}

    approved = approver(changes)
    if not approved:
        audit.append_audit(
            audit.make_audit_record(
                target.name, admin, instruction, changes, None, approved=False
            ),
            audit_log,
        )
        return {"status": "aborted", "changed_fields": changes}

    archive = audit.archive_version(target.file_path, versions_dir)
    _write_json(target.file_path, draft)
    audit.append_audit(
        audit.make_audit_record(
            target.name, admin, instruction, changes, str(archive), approved=True
        ),
        audit_log,
    )
    return {
        "status": "applied",
        "changed_fields": changes,
        "version_archived": str(archive),
    }


def rollback(
    target: EditableTarget,
    version_path: Path,
    admin: str,
    *,
    audit_log: Path | None = None,
    versions_dir: Path | None = None,
) -> dict:
    """Restore a target to an archived version. Single-step but audited.

    Safety: the version file must live inside the versions directory and pass
    schema validation before it is restored.
    """
    versions_dir = versions_dir or (target.file_path.parent / "_versions")
    version_path = version_path.resolve()
    # Path-traversal guard: must be inside versions_dir.
    if versions_dir.resolve() not in version_path.parents:
        return {"status": "rejected", "reason": "invalid_version_path"}
    if not version_path.exists():
        return {"status": "rejected", "reason": "version_not_found"}

    restored = _read_json(version_path)
    ok, err = schemas.validate_draft(target.schema, restored)
    if not ok:
        return {"status": "rejected", "reason": "validation_failed", "error": err}

    current = _read_json(target.file_path)
    changes = audit.compute_diff(current, restored)
    if not changes:
        return {"status": "no_change", "changed_fields": []}

    archive = audit.archive_version(target.file_path, versions_dir)
    _write_json(target.file_path, restored)
    audit.append_audit(
        audit.make_audit_record(
            target.name, admin, f"rollback to {version_path.name}",
            changes, str(archive), approved=True, action="rollback",
        ),
        audit_log,
    )
    return {"status": "rolled_back", "changed_fields": changes,
            "version_archived": str(archive), "restored_from": version_path.name}


def _interactive_approver(changes: list[str]) -> bool:
    print("\nThe following fields will change:")
    for c in changes:
        print(f"  - {c}")
    return input("\nConfirm write? (y/n): ").strip().lower() == "y"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Admin natural-language authoring tool")
    parser.add_argument("target", nargs="?", choices=all_target_names())
    parser.add_argument("--admin", default="unknown", help="Operator name (recorded in audit log)")
    parser.add_argument("--instruction", help="Natural-language edit instruction (interactive if omitted)")
    parser.add_argument("--list", action="store_true", help="List editable data targets")
    args = parser.parse_args(argv)

    if args.list or not args.target:
        print("Editable data:")
        for name in all_target_names():
            t = get_target(name)
            print(f"  {name}  (risk: {t.risk}) - {t.description[:50]}...")
        return 0

    target = get_target(args.target)
    instruction = args.instruction or input("Enter a natural-language edit instruction:\n> ")

    current = _read_json(target.file_path)

    from .extract import ExtractionError, extract

    print("\nCalling DeepSeek to generate draft...")
    try:
        draft = extract(target, current, instruction)
    except ExtractionError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1

    result = apply_draft(target, draft, instruction, args.admin, _interactive_approver)

    if result["status"] == "rejected":
        print(f"\n[Draft validation failed; nothing written]\n{result['error']}", file=sys.stderr)
        return 1
    if result["status"] == "no_change":
        print("\nDraft is identical to current content; no changes.")
        return 0
    if result["status"] == "aborted":
        print("\nCancelled; nothing written.")
        return 0
    print(f"\nWritten. Previous version archived: {result['version_archived']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
