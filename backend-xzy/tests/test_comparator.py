"""Deterministic tests for #6 comparator v2 (derivation + scoring + weighting)."""
from agents.comparator.agent import handle
from agents.comparator.engine import (
    compare,
    derive_role_strengths,
    parse_fee_sgd,
    parse_min_months,
)
from common import mock_data
from common.profile import TargetRole

PROGRAMS = {
    "NUS MSc in Digital Financial Technology",
    "SMU MSc in Applied Finance (FinTech track)",
    "NTU MSc in Financial Technology",
    "SMU MITB (Financial Technology & Analytics)",
    "HKUST MSc in Financial Technology",
}


# ---------- dataset shape ----------
def test_five_real_programs_eleven_dimensions():
    comp = compare([TargetRole.fintech_pm])
    assert {r.program for r in comp.rows} == PROGRAMS
    assert len(comp.dimensions) == 11
    assert {"intake", "scholarship", "gmat_gre",
            "typical_profile", "industry_orientation",
            "technical_depth", "career_pathways"} <= set(comp.dimensions)


def test_rows_carry_provenance():
    for r in compare([TargetRole.fintech_pm]).rows:
        assert r.source_url and r.fetched_at


# ---------- role derivation (explainable) ----------
def test_derivation_finds_roles_with_reasons():
    roles, reasons = derive_role_strengths("金融自动化、区块链、数据科学、机器学习、数字金融服务")
    assert "payments" in roles and "区块链" in reasons["payments"]
    assert "data_analytics" in roles  # 数据/机器学习


def test_derivation_empty_text():
    roles, reasons = derive_role_strengths("")
    assert roles == [] and reasons == {}


def test_matched_roles_intersect_target_with_reasons():
    comp = compare([TargetRole.quant_risk])
    nus = next(r for r in comp.rows if r.program.startswith("NUS"))
    assert "quant_risk" in nus.synthesis.matched_roles
    assert nus.synthesis.role_reasons["quant_risk"]


# ---------- scoring helpers ----------
def test_parse_fee_sgd_currencies():
    assert parse_fee_sgd("S$63,220(含 GST)") == 63220
    assert parse_fee_sgd("HK$395,000") == 395000 * 0.17
    assert parse_fee_sgd("官方未公开") is None


def test_parse_min_months():
    assert parse_min_months("18 个月") == 18
    assert parse_min_months("1 年(全日制)/ 2 年(兼读)") == 12
    assert parse_min_months("1-2 年(全日制)") == 12
    assert parse_min_months("未明确公布") is None


# ---------- weighting ----------
def test_default_weight_is_role_fit():
    comp = compare([TargetRole.fintech_pm])
    assert comp.weights == {"role_fit": 1.0}


def test_weights_normalised():
    comp = compare([TargetRole.fintech_pm], {"cost": 3, "role_fit": 1})
    assert abs(sum(comp.weights.values()) - 1.0) < 1e-9
    assert abs(comp.weights["cost"] - 0.75) < 1e-9


def test_cost_priority_changes_best_fit():
    comp = compare([TargetRole.fintech_pm], {"cost": 0.9, "role_fit": 0.1})
    best = max(comp.rows, key=lambda r: r.synthesis.weighted_score)
    assert best.synthesis.weighted_score == comp.rows[0].synthesis.weighted_score \
        or best.program == comp.best_for_you
    cheapest = min(
        (r for r in comp.rows if _verified_text(r.facts, "fees") is not None),
        key=lambda r: parse_fee_sgd(_verified_text(r.facts, "fees")) or 1e9,
    )
    assert cheapest.synthesis.score_breakdown["cost"] == 1.0


def test_target_wins_ties():
    comp = compare([TargetRole.fintech_pm, TargetRole.quant_risk])
    assert "Digital Financial Technology" in comp.best_for_you  # NUS via target tiebreak


# ---------- compliance + envelope ----------
def test_envelope_has_facts_table_and_synthesis_zones():
    resp = handle(mock_data.get_profile("1"))
    d = resp.data
    assert set(d["facts_table"]["rows"][0]["facts"]["fees"]) == {
        "text", "kind", "source_url", "fetched_at"}
    assert all(cell["source_url"] is None
               for r in d["facts_table"]["rows"]
               for cell in r["facts"].values() if cell["kind"] != "verified")
    assert d["synthesis"]["best_for_you"] is not None
    assert d["synthesis"]["weights"]
    assert "排名" in d["disclaimer"]


def test_priorities_via_slots():
    resp = handle(mock_data.get_profile("1"), {"priorities": {"cost": 1.0}})
    assert resp.data["synthesis"]["weights"] == {"cost": 1.0}


def test_narrative_offline_deterministic():
    p = mock_data.get_profile("1")
    assert handle(p).data["synthesis"]["narrative"] == handle(p).data["synthesis"]["narrative"]


def test_ranking_narrative_falls_back(monkeypatch):
    from agents.comparator import agent as cagent
    monkeypatch.setattr(cagent.llm, "available", lambda: True)
    monkeypatch.setattr(cagent.llm, "explain", lambda *a, **k: "NUS 优于其他所有项目,排名第一")
    resp = handle(mock_data.get_profile("1"))
    assert "优于" not in resp.data["synthesis"]["narrative"]
    assert "排名" not in resp.data["synthesis"]["narrative"]


# ---------- v3: three-state cell normalization ----------
from agents.comparator.engine import FactCell, RowSynthesis, _normalize_cell, _verified_text


def test_row_has_facts_and_synthesis_split():
    comp = compare([TargetRole.fintech_pm])
    r = comp.rows[0]
    assert isinstance(r.facts, dict) and isinstance(r.facts["fees"], FactCell)
    assert isinstance(r.synthesis, RowSynthesis)
    assert set(r.synthesis.score_breakdown) == {"role_fit", "cost", "duration"}


def test_unknown_fee_scores_neutral_cost():
    comp = compare([TargetRole.fintech_pm])
    ntu = next(r for r in comp.rows if r.program.startswith("NTU"))
    assert ntu.facts["fees"].kind == "unknown"
    assert ntu.synthesis.score_breakdown["cost"] == 0.5


def test_synthesis_cells_never_affect_role_fit():
    comp = compare([TargetRole.payments])
    for r in comp.rows:
        derived, _ = derive_role_strengths(_verified_text(r.facts, "curriculum_focus") or "")
        assert set(r.synthesis.matched_roles) <= set(derived)


def test_normalize_bare_string_is_verified_with_row_source():
    cell = _normalize_cell("S$74,120", "http://x", "2026-06-05")
    assert cell == FactCell(text="S$74,120", kind="verified",
                            source_url="http://x", fetched_at="2026-06-05")


def test_normalize_object_synthesis_drops_inherited_source():
    cell = _normalize_cell({"text": "深度高", "kind": "synthesis"}, "http://x", "2026-06-05")
    assert cell.kind == "synthesis"
    assert cell.source_url is None and cell.fetched_at is None


def test_normalize_object_unknown_kind_preserved():
    cell = _normalize_cell({"text": "未公开", "kind": "unknown"}, "http://x", "2026-06-05")
    assert cell.kind == "unknown" and cell.text == "未公开"


def test_normalize_object_bad_kind_falls_back_to_verified():
    cell = _normalize_cell({"text": "x", "kind": "bogus"}, "http://x", "2026-06-05")
    assert cell.kind == "verified"


def test_verified_text_only_returns_verified():
    facts = {
        "fees": FactCell("S$1", "verified", "u", "d"),
        "intake": FactCell("未公开", "unknown"),
        "technical_depth": FactCell("高", "synthesis"),
    }
    assert _verified_text(facts, "fees") == "S$1"
    assert _verified_text(facts, "intake") is None
    assert _verified_text(facts, "technical_depth") is None
    assert _verified_text(facts, "missing") is None


# ---------- v3: anti-ranking guard ----------
from agents.comparator.engine import violates_ranking


def test_ranking_phrases_are_flagged():
    for bad in [
        "NUS 优于 NTU", "这个项目更好", "综合排名第一", "NUS is better than SMU",
        "the best programme for fintech", "NTU outperforms HKUST", "ranked top",
        # plural noun heads must also be caught (regression for the \b bypass)
        "the best programmes for fintech", "these are the best programs",
        "top programmes overall", "the best options", "best schools",
    ]:
        assert violates_ranking(bad), bad


def test_fit_language_is_allowed():
    for ok in [
        "结合你的目标,NUS 在支付方向更契合你", "best fit for your goals",
        "最适合你的目标的是 NUS DFT", "各项目各有侧重,建议按目标权衡。",
        # 更好地<动词> is adverbial fit phrasing, not a cross-programme ranking
        "更好地契合你的目标", "帮助你更好地规划路径",
    ]:
        assert not violates_ranking(ok), ok


# ---------- v3: schema accepts three-state cells ----------
from admin.schemas import ProgramsDataset, validate_draft


def _min_dataset(values):
    return {
        "dimensions": list(values.keys()),
        "disclaimer": "对比基于公开整理数据,不构成排名。",
        "programs": [{
            "program": "X", "is_target": True,
            "source_url": "http://x", "fetched_at": "2026-06-05",
            "values": values,
        }],
    }


def test_schema_accepts_bare_string_and_cell_objects():
    draft = _min_dataset({
        "fees": "S$1",
        "intake": {"text": "未公开", "kind": "unknown"},
        "technical_depth": {"text": "高", "kind": "synthesis"},
    })
    ok, err = validate_draft(ProgramsDataset, draft)
    assert ok, err


def test_schema_rejects_bad_kind():
    draft = _min_dataset({"fees": {"text": "x", "kind": "bogus"}})
    ok, err = validate_draft(ProgramsDataset, draft)
    assert not ok


# ---------- v3: dataset has 11 dims incl 4 new, validates, has 3 kinds ----------
import json as _json
from pathlib import Path as _Path


def test_dataset_has_new_dimensions_and_validates():
    raw = _json.loads((_Path("data") / "programs_dataset.json").read_text(encoding="utf-8"))
    dims = set(raw["dimensions"])
    assert {"typical_profile", "industry_orientation",
            "technical_depth", "career_pathways"} <= dims
    ok, err = validate_draft(ProgramsDataset, raw)
    assert ok, err


def test_dataset_exercises_all_three_kinds():
    comp = compare([TargetRole.fintech_pm])
    kinds = {c.kind for r in comp.rows for c in r.facts.values()}
    assert kinds == {"verified", "unknown", "synthesis"}
