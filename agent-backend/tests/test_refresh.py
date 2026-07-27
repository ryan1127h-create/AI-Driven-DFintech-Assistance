"""Tests for the refresh pipeline (offline; SampleFetcher/StaticFetcher)."""
import json
from pathlib import Path

import pytest

from admin import schemas
from refresh import anomaly, pending, pipeline, tiering
from datetime import date

from refresh.fetcher import StaticFetcher, _candidate_acad_years, map_nusmods_module, resolve_acad_year
from refresh.sources import RefreshSource, catalog_target_codes


def _catalog(modules) -> dict:
    return {"source_url": "https://x", "fetched_at": "2026-05-31", "modules": modules}


_BASE = [
    {"code": "DFT5101", "name": "A", "credits": 4},
    {"code": "DFT5102", "name": "B", "credits": 4},
]


# ---------- anomaly ----------
def test_anomaly_detects_removed():
    cur = _catalog(_BASE)
    draft = _catalog(_BASE[:1])
    assert anomaly.detect_catalog_anomalies(cur, draft) == ["module_removed: DFT5102"]


def test_anomaly_detects_name_and_credits_change():
    cur = _catalog(_BASE)
    draft = _catalog([{"code": "DFT5101", "name": "A2", "credits": 5},
                      {"code": "DFT5102", "name": "B", "credits": 4}])
    a = anomaly.detect_catalog_anomalies(cur, draft)
    assert "name_changed: DFT5101" in a and "credits_changed: DFT5101" in a


def test_anomaly_addition_is_not_flagged():
    cur = _catalog(_BASE)
    draft = _catalog(_BASE + [{"code": "DFT5103", "name": "C", "credits": 4}])
    assert anomaly.detect_catalog_anomalies(cur, draft) == []


# ---------- tiering ----------
def test_tiering_rejects_invalid_schema():
    d = tiering.decide(schema_ok=False, is_first_load=False, trusted=True, anomalies=[])
    assert d.action == "rejected"


def test_tiering_first_load_needs_review():
    d = tiering.decide(schema_ok=True, is_first_load=True, trusted=True, anomalies=[])
    assert d.action == "needs_review" and d.reasons == ["first_onboarding"]


def test_tiering_anomaly_needs_review():
    d = tiering.decide(schema_ok=True, is_first_load=False, trusted=True, anomalies=["module_removed: X"])
    assert d.action == "needs_review"


def test_tiering_untrusted_needs_review():
    d = tiering.decide(schema_ok=True, is_first_load=False, trusted=False, anomalies=[])
    assert d.action == "needs_review"


def test_tiering_clean_trusted_auto_publishes():
    d = tiering.decide(schema_ok=True, is_first_load=False, trusted=True, anomalies=[])
    assert d.action == "auto_publish"


# ---------- programs_dataset (competitor data) ----------
def test_programs_anomaly_detects_removal_and_fee_change():
    cur = {"programs": [
        {"program": "A", "values": {"fees": "100", "duration": "1y"}},
        {"program": "B", "values": {"fees": "200", "duration": "1y"}},
    ]}
    draft = {"programs": [
        {"program": "A", "values": {"fees": "999", "duration": "1y"}},  # fee change
    ]}
    a = anomaly.detect_programs_anomalies(cur, draft)
    assert "program_removed: B" in a and "fees_changed: A" in a


def test_programs_schema_requires_provenance():
    bad = {"dimensions": ["fees"], "disclaimer": "d",
           "programs": [{"program": "X", "is_target": True, "values": {"fees": "1"}}]}  # no source_url
    ok, err = schemas.validate_draft(schemas.ProgramsDataset, bad)
    assert not ok


def test_programs_competitor_data_never_auto_published(tmp_path, monkeypatch):
    # A trusted=false source must always route to review, even with no anomalies.
    src = RefreshSource(
        name="programs_dataset", file_path=tmp_path / "p.json",
        schema=schemas.ProgramsDataset, trusted=False,
        anomaly_fn=anomaly.detect_programs_anomalies,
        default_fetcher=StaticFetcher({}),
    )
    src.file_path.write_text(json.dumps({
        "dimensions": ["fees"], "disclaimer": "d",
        "programs": [{"program": "NUS", "is_target": True, "source_url": "u",
                      "fetched_at": "2026-05-31", "values": {"fees": "1"}}],
    }), encoding="utf-8")
    monkeypatch.setattr("refresh.pipeline.get_source", lambda n: src)
    same = json.loads(src.file_path.read_text(encoding="utf-8"))
    res = pipeline.run("programs_dataset", fetcher=StaticFetcher(same),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v",
                       pending_dir=tmp_path / "_p")
    assert res["status"] == "queued_for_review"
    assert "untrusted_source" in res["reasons"]


# ---------- NUSMods mapper (offline; static fixture) ----------
def test_map_nusmods_module():
    raw = {"moduleCode": "BMS5312", "title": "Fintech Management",
           "moduleCredit": "4", "description": "An overview..."}
    m = map_nusmods_module(raw)
    assert m["code"] == "BMS5312"
    assert m["name"] == "Fintech Management"
    assert m["credits"] == 4  # string "4" -> int
    assert m["source_url"] == "https://nusmods.com/courses/BMS5312"


def test_map_nusmods_handles_missing_credit():
    m = map_nusmods_module({"moduleCode": "X1", "title": "T"})
    assert m["credits"] is None and m["description"] is None


def test_candidate_years_most_recent_first():
    # Before August -> current academic year started the previous calendar year.
    ys = _candidate_acad_years(date(2026, 5, 31))
    assert ys[0] == "2025-2026"
    ys2 = _candidate_acad_years(date(2026, 9, 1))  # after August
    assert ys2[0] == "2026-2027"


def test_resolve_acad_year_env_override(monkeypatch):
    monkeypatch.setenv("NUSMODS_ACAD_YEAR", "2019-2020")
    assert resolve_acad_year(probe=False) == "2019-2020"


def test_resolve_acad_year_no_probe_returns_latest(monkeypatch):
    monkeypatch.delenv("NUSMODS_ACAD_YEAR", raising=False)
    assert resolve_acad_year(probe=False) == _candidate_acad_years()[0]


def test_catalog_target_codes_from_role_map():
    codes = catalog_target_codes()
    assert "DBA5109" in codes and "BMS5312" in codes  # real codes, unique+sorted
    assert codes == sorted(set(codes))


# ---------- pipeline end-to-end (temp target) ----------
def _source(tmp_path, trusted=True) -> RefreshSource:
    f = tmp_path / "module_catalog.json"
    f.write_text(json.dumps(_catalog(_BASE), ensure_ascii=False), encoding="utf-8")
    return RefreshSource(
        name="module_catalog", file_path=f, schema=schemas.ModuleCatalog,
        trusted=trusted, anomaly_fn=anomaly.detect_catalog_anomalies,
        default_fetcher=StaticFetcher(_catalog(_BASE)),
    )


@pytest.fixture(autouse=True)
def _patch_source(monkeypatch, tmp_path):
    """Point refresh.sources at a temp source so the real data is untouched."""
    src = _source(tmp_path)
    monkeypatch.setattr("refresh.pipeline.get_source", lambda name: src)
    return src


def test_pipeline_auto_publishes_addition(tmp_path, _patch_source):
    src = _patch_source
    fetched = _catalog(_BASE + [{"code": "DFT5103", "name": "C", "credits": 4}])
    res = pipeline.run("module_catalog", fetcher=StaticFetcher(fetched),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v")
    assert res["status"] == "auto_published"
    written = json.loads(src.file_path.read_text(encoding="utf-8"))
    assert len(written["modules"]) == 3


def test_pipeline_no_change(tmp_path, _patch_source):
    res = pipeline.run("module_catalog", fetcher=StaticFetcher(_catalog(_BASE)),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v")
    assert res["status"] == "no_change"


def test_pipeline_queues_on_anomaly(tmp_path, _patch_source):
    removed = _catalog(_BASE[:1])  # a module vanished -> anomaly
    res = pipeline.run("module_catalog", fetcher=StaticFetcher(removed),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v",
                       pending_dir=tmp_path / "_pending")
    assert res["status"] == "queued_for_review"
    assert any("module_removed" in r for r in res["anomalies"])
    # target file NOT modified
    assert len(json.loads(_patch_source.file_path.read_text(encoding="utf-8"))["modules"]) == 2


def test_pipeline_rejects_invalid(tmp_path, _patch_source):
    bad = {"source_url": "", "fetched_at": "", "modules": []}  # invalid
    res = pipeline.run("module_catalog", fetcher=StaticFetcher(bad),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v")
    assert res["status"] == "rejected"


def test_approve_pending_publishes(tmp_path, _patch_source):
    src = _patch_source
    removed = _catalog(_BASE[:1])
    res = pipeline.run("module_catalog", fetcher=StaticFetcher(removed),
                       audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v",
                       pending_dir=tmp_path / "_pending")
    pfile = res["pending_file"]
    # approve it
    ap = pipeline.approve_pending(pfile, admin="alice",
                                  audit_log=tmp_path / "a.jsonl", versions_dir=tmp_path / "_v")
    assert ap["status"] == "approved"
    assert len(json.loads(src.file_path.read_text(encoding="utf-8"))["modules"]) == 1
    # pending marked resolved
    assert pending.load(pfile)["status"] == "resolved"
