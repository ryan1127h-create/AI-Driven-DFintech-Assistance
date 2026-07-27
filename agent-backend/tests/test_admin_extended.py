"""Tests for admissions_rules schema, rollback core, and history/rollback web routes."""
import json
from pathlib import Path

import pytest

from admin import audit, schemas, webapp
from admin.author import rollback
from admin.registry import EditableTarget, get_target


# ---------- admissions_rules schema ----------
def _valid_rules() -> dict:
    return {
        "_comment": "test",
        "base_items": [{"key": "cv", "label": "CV", "why": "background"}],
        "conditional_items": [
            {"key": "eng", "label": "English", "why": "lang",
             "applies_when": {"english_proof_required": True}},
        ],
        "english_exempt_countries": ["SG"],
        "local_institution_keywords": ["nus"],
        "low_experience_threshold_years": 1,
    }


def test_admissions_rules_valid():
    ok, err = schemas.validate_draft(schemas.AdmissionsRules, _valid_rules())
    assert ok, err


def test_admissions_rules_rejects_unsupported_condition():
    d = _valid_rules()
    d["conditional_items"][0]["applies_when"] = {"mystery_condition": True}
    ok, err = schemas.validate_draft(schemas.AdmissionsRules, d)
    assert not ok and "unsupported" in err.lower()


def test_admissions_rules_rejects_duplicate_keys():
    d = _valid_rules()
    d["base_items"].append({"key": "cv", "label": "x", "why": "y"})
    ok, err = schemas.validate_draft(schemas.AdmissionsRules, d)
    assert not ok and "duplicate" in err.lower()


def test_admissions_rules_rejects_empty_base_items():
    d = _valid_rules()
    d["base_items"] = []
    ok, _ = schemas.validate_draft(schemas.AdmissionsRules, d)
    assert not ok


def test_real_admissions_file_validates():
    t = get_target("admissions_rules")
    cur = json.loads(t.file_path.read_text(encoding="utf-8"))
    ok, err = schemas.validate_draft(t.schema, cur)
    assert ok, err


# ---------- rollback core (temp files) ----------
def _st_target(tmp_path: Path) -> EditableTarget:
    codes = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "DOCS_REQUIRED",
             "OFFER", "WAITLIST", "REJECTED", "ACCEPTED"]
    content = {"translations": {c: {"human_status": f"h_{c}", "next_step": f"n_{c}"} for c in codes}}
    f = tmp_path / "status_translations.json"
    f.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return EditableTarget(
        name="status_translations", file_path=f,
        schema=schemas.StatusTranslations, edit_key="translations",
        risk="low", description="t",
    )


def test_rollback_restores_and_audits(tmp_path):
    t = _st_target(tmp_path)
    versions = tmp_path / "_versions"
    audit_log = tmp_path / "audit.jsonl"

    # archive the original, then mutate the live file
    original = json.loads(t.file_path.read_text(encoding="utf-8"))
    archive = audit.archive_version(t.file_path, versions)
    mutated = json.loads(json.dumps(original))
    mutated["translations"]["OFFER"]["next_step"] = "changed"
    t.file_path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")

    result = rollback(t, archive, "alice", audit_log=audit_log, versions_dir=versions)
    assert result["status"] == "rolled_back"
    # file restored to original
    now = json.loads(t.file_path.read_text(encoding="utf-8"))
    assert now["translations"]["OFFER"]["next_step"] == "n_OFFER"
    # audited as rollback
    rec = json.loads(audit_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["action"] == "rollback" and rec["approved"] is True


def test_rollback_rejects_path_traversal(tmp_path):
    t = _st_target(tmp_path)
    outside = tmp_path / "evil.json"
    outside.write_text("{}", encoding="utf-8")
    result = rollback(t, outside, "alice",
                      audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_versions")
    assert result["status"] == "rejected" and result["reason"] == "invalid_version_path"


def test_rollback_no_change_when_identical(tmp_path):
    t = _st_target(tmp_path)
    versions = tmp_path / "_versions"
    archive = audit.archive_version(t.file_path, versions)  # identical to current
    result = rollback(t, archive, "alice", audit_log=tmp_path / "a.jsonl", versions_dir=versions)
    assert result["status"] == "no_change"


# ---------- web routes ----------
@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_history_page_renders(client):
    resp = client.get("/history")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "版本回滚" in body and "审计日志" in body


def test_rollback_route_rejects_bad_version(client):
    # nonexistent version name -> rejected, no crash
    resp = client.post("/rollback", data={
        "target": "status_translations", "admin": "x", "version": "nope.json"})
    assert resp.status_code == 200
    assert "被拒绝" in resp.get_data(as_text=True)
