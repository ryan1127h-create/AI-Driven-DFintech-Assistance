"""Tests for the admin authoring pipeline (no LLM; uses temp files)."""
import json
from pathlib import Path

import pytest

from admin import audit, schemas
from admin.author import apply_draft
from admin.registry import EditableTarget


def _full_translations() -> dict:
    codes = [
        "DRAFT", "SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED",
        "OFFER", "WAITLIST", "REJECTED", "ACCEPTED",
    ]
    return {
        "_comment": "test",
        "translations": {
            c: {"human_status": f"hs_{c}", "next_step": f"ns_{c}"} for c in codes
        },
    }


# ---------- schema validation ----------
def test_valid_draft_passes():
    ok, err = schemas.validate_draft(schemas.StatusTranslations, _full_translations())
    assert ok and err is None


def test_missing_status_code_rejected():
    d = _full_translations()
    del d["translations"]["OFFER"]
    ok, err = schemas.validate_draft(schemas.StatusTranslations, d)
    assert not ok and "missing" in err.lower()


def test_unknown_status_code_rejected():
    d = _full_translations()
    d["translations"]["BOGUS"] = {"human_status": "x", "next_step": "y"}
    ok, err = schemas.validate_draft(schemas.StatusTranslations, d)
    assert not ok and "unknown" in err.lower()


def test_empty_field_rejected():
    d = _full_translations()
    d["translations"]["DRAFT"]["next_step"] = ""
    ok, err = schemas.validate_draft(schemas.StatusTranslations, d)
    assert not ok


# ---------- diff ----------
def test_diff_detects_modified_leaf():
    a = _full_translations()
    b = _full_translations()
    b["translations"]["UNDER_REVIEW"]["next_step"] = "changed"
    changes = audit.compute_diff(a, b)
    assert changes == ["translations.UNDER_REVIEW.next_step"]


def test_diff_empty_when_identical():
    assert audit.compute_diff(_full_translations(), _full_translations()) == []


# ---------- apply_draft end-to-end (no LLM) ----------
def _target(tmp_path: Path) -> EditableTarget:
    f = tmp_path / "status_translations.json"
    f.write_text(json.dumps(_full_translations(), ensure_ascii=False), encoding="utf-8")
    return EditableTarget(
        name="status_translations",
        file_path=f,
        schema=schemas.StatusTranslations,
        edit_key="translations",
        risk="low",
        description="test",
    )


def test_apply_draft_writes_and_audits_on_approval(tmp_path):
    t = _target(tmp_path)
    draft = _full_translations()
    draft["translations"]["UNDER_REVIEW"]["next_step"] = "预计3周内出结果"
    audit_log = tmp_path / "audit.jsonl"
    versions = tmp_path / "_versions"

    result = apply_draft(
        t, draft, "改 UNDER_REVIEW 下一步", "alice", lambda c: True,
        audit_log=audit_log, versions_dir=versions,
    )
    assert result["status"] == "applied"
    # file actually updated
    written = json.loads(t.file_path.read_text(encoding="utf-8"))
    assert written["translations"]["UNDER_REVIEW"]["next_step"] == "预计3周内出结果"
    # version archived
    assert list(versions.glob("status_translations.*.json"))
    # audit recorded, approved=True, instruction + changed fields captured
    rec = json.loads(audit_log.read_text(encoding="utf-8").strip())
    assert rec["approved"] is True
    assert rec["admin"] == "alice"
    assert rec["changed_fields"] == ["translations.UNDER_REVIEW.next_step"]


def test_apply_draft_aborts_without_write_on_rejection(tmp_path):
    t = _target(tmp_path)
    before = t.file_path.read_text(encoding="utf-8")
    draft = _full_translations()
    draft["translations"]["DRAFT"]["next_step"] = "new"
    audit_log = tmp_path / "audit.jsonl"

    result = apply_draft(
        t, draft, "x", "bob", lambda c: False, audit_log=audit_log,
        versions_dir=tmp_path / "_v",
    )
    assert result["status"] == "aborted"
    assert t.file_path.read_text(encoding="utf-8") == before  # unchanged
    rec = json.loads(audit_log.read_text(encoding="utf-8").strip())
    assert rec["approved"] is False  # rejection still audited


def test_apply_draft_rejects_invalid_draft_without_write(tmp_path):
    t = _target(tmp_path)
    before = t.file_path.read_text(encoding="utf-8")
    bad = _full_translations()
    del bad["translations"]["OFFER"]  # invalid
    result = apply_draft(
        t, bad, "x", "bob", lambda c: True,
        audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v",
    )
    assert result["status"] == "rejected"
    assert t.file_path.read_text(encoding="utf-8") == before


def test_apply_draft_no_change(tmp_path):
    t = _target(tmp_path)
    result = apply_draft(
        t, _full_translations(), "x", "bob", lambda c: True,
        audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v",
    )
    assert result["status"] == "no_change"
