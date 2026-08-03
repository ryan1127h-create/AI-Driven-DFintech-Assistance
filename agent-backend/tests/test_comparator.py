"""Deterministic tests for #6 comparator v2 (derivation + scoring + weighting)."""
import json as _json
from pathlib import Path as _Path

from app.agents.comparator import engine
from app.agents.comparator.agent import handle
from app.agents.comparator.engine import (
    compare,
    derive_role_strengths,
    parse_fee_sgd,
    parse_min_months,
)
from common import mock_data
from common.profile import TargetRole

# Anchored on this file, not the cwd: pytest is run from the project parent dir,
# so a relative "data/..." path would not resolve.
_DATASET_PATH = _Path(__file__).resolve().parents[1] / "data" / "programs_dataset.json"

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
    roles, reasons = derive_role_strengths(
        "financial automation, blockchain, data science, machine learning, "
        "digital financial services"
    )
    assert "payments" in roles and "blockchain" in reasons["payments"]
    assert "data_analytics" in roles and "machine learning" in reasons["data_analytics"]
    assert "digital_banking" in roles
    assert "digital financial services" in reasons["digital_banking"]


def test_derivation_empty_text():
    roles, reasons = derive_role_strengths("")
    assert roles == [] and reasons == {}


def test_keyword_needs_word_boundary():
    # "ai" used to match inside "blockchain"/"training" under bare containment.
    roles, _ = derive_role_strengths("Blockchain and training rails")
    assert "data_analytics" not in roles
    _, reasons = derive_role_strengths("AI and data science")
    assert "ai" in reasons["data_analytics"]


def test_keyword_still_matches_plural():
    _, reasons = derive_role_strengths("Digital Financial Transactions and Risk Management")
    assert "transaction" in reasons["payments"]


def test_multi_word_keyword_matches_hyphenated_variant():
    # Separator tolerance, not a claim about any real page: re.escape() made the
    # keyword table's own separator mandatory, so matching depended on which one a
    # dataset refresh happened to use. No shipped text is hyphenated today.
    _, reasons = derive_role_strengths("Machine-learning and data-science electives")
    assert "machine learning" in reasons["data_analytics"]
    assert "data science" in reasons["data_analytics"]


def test_roles_without_curriculum_evidence_score_zero():
    """Truthful zero for roles the verified curriculum text does not evidence.

    Regression guard for two evidence misattributions that must not come back:
      - "risk management" credited compliance_regtech, but risk management is not
        compliance/RegTech -- the score was real, the justifying text was wrong.
      - "fintech" / "financial technology" credited fintech_pm, but all five
        programmes carry FinTech in their own name, so the match restated the
        title rather than evidencing curriculum fit (and dropping only the
        two-word spelling left SMU MITB alone at 0.0 purely because its text
        writes "Financial Technology", a false negative driven by spelling).
    Only add genuine evidence to the dataset to change this expectation.
    """
    for role in (TargetRole.compliance_regtech, TargetRole.fintech_pm):
        fits = {r.program: r.synthesis.score_breakdown["role_fit"]
                for r in compare([role]).rows}
        assert set(fits.values()) == {0.0}, f"{role.value} claims evidence: {fits}"


def test_digital_banking_differentiates_via_verified_evidence():
    # NTU's curriculum_focus names "Digital Financial Services" verbatim; it is a
    # specialisation, not the programme title, so the discrimination is real.
    fits = {r.program: r.synthesis.score_breakdown["role_fit"]
            for r in compare([TargetRole.digital_banking]).rows}
    ntu = next(p for p in fits if p.startswith("NTU"))
    assert fits[ntu] == 1.0
    assert set(fits.values()) == {0.0, 1.0}, fits


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
    """A cost-dominant weighting must move the recommendation to the cheapest row.

    The expectation is derived from the fee cells, never from weighted_score:
    fintech_pm has no curriculum evidence anywhere, so role_fit is 0.0 for every
    row and the cost criterion alone decides. Under the default role_fit-only
    weighting there is therefore no recommendation at all -- that is the "change".
    """
    assert compare([TargetRole.fintech_pm]).best_for_you is None
    comp = compare([TargetRole.fintech_pm], {"cost": 0.9, "role_fit": 0.1})
    cheapest = min(
        (r for r in comp.rows if _verified_text(r.facts, "fees") is not None),
        key=lambda r: parse_fee_sgd(_verified_text(r.facts, "fees")) or 1e9,
    )
    assert cheapest.synthesis.score_breakdown["cost"] == 1.0
    assert comp.best_for_you == cheapest.program


def test_best_for_you_is_the_row_with_the_most_role_evidence():
    # NUS is the only programme whose curriculum evidences quant_risk, so it wins
    # on score alone. This does NOT exercise the is_target tiebreak: NUS is also
    # the first dataset row, so max() returns it either way -- see
    # test_is_target_breaks_a_weighted_score_tie for that.
    comp = compare([TargetRole.fintech_pm, TargetRole.quant_risk])
    assert "Digital Financial Technology" in comp.best_for_you


def _tie_dataset() -> dict:
    """Two indistinguishable programmes, the target one deliberately NOT first."""
    shared = {
        "curriculum_focus": "Blockchain and payment transaction rails.",
        "duration": "1 year full-time.",
        "fees": "S$50,000 tuition fee.",
    }
    return {
        "dimensions": list(shared),
        "disclaimer": "Fit analysis only, not a ranking.",
        "programs": [
            {"program": "Rival", "is_target": False, "source_url": "http://x",
             "fetched_at": "2026-06-05", "values": dict(shared)},
            {"program": "Target", "is_target": True, "source_url": "http://x",
             "fetched_at": "2026-06-05", "values": dict(shared)},
        ],
    }


def test_is_target_breaks_a_weighted_score_tie(monkeypatch):
    """On an exact score tie the target programme must be the one surfaced.

    The shipped dataset cannot show this: NUS is both the target and row 0, so
    max() returns it with or without the tiebreak. Ordering the target row last
    makes the tiebreak the only thing that decides.
    """
    monkeypatch.setattr(engine, "_load", _tie_dataset)
    comp = compare([TargetRole.payments])
    assert [r.synthesis.weighted_score for r in comp.rows] == [1.0, 1.0]
    assert comp.best_for_you == "Target"


def test_no_evidence_yields_no_best_for_you():
    """Every row scoring zero must produce no recommendation at all.

    compliance_regtech has no curriculum evidence in any row (see
    test_roles_without_curriculum_evidence_score_zero), so the zero guard is the
    only thing between the user and a "best fit" backed by nothing.
    """
    comp = compare([TargetRole.compliance_regtech])
    assert [r.synthesis.weighted_score for r in comp.rows] == [0.0] * len(comp.rows)
    assert comp.best_for_you is None


def test_no_best_fit_is_explained_to_the_user():
    """The absence of a recommendation must be stated, not silently omitted."""
    profile = mock_data.get_profile("1").model_copy(
        update={"target_roles": [TargetRole.compliance_regtech]})
    resp = handle(profile)
    assert resp.data["synthesis"]["best_for_you"] is None
    narrative = resp.data["synthesis"]["narrative"]
    assert narrative == resp.speakable
    assert "no single best fit is highlighted" in narrative
    assert not engine.violates_ranking(narrative)


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
    assert "not a ranking" in d["disclaimer"]


def test_priorities_via_slots():
    resp = handle(mock_data.get_profile("1"), {"priorities": {"cost": 1.0}})
    assert resp.data["synthesis"]["weights"] == {"cost": 1.0}


def test_narrative_offline_deterministic():
    p = mock_data.get_profile("1")
    assert handle(p).data["synthesis"]["narrative"] == handle(p).data["synthesis"]["narrative"]


def test_ranking_narrative_falls_back(monkeypatch):
    from app.agents.comparator import agent as cagent
    monkeypatch.setattr(cagent.llm, "available", lambda: True)
    monkeypatch.setattr(cagent.llm, "explain", lambda *a, **k: "NUS 优于其他所有项目,排名第一")
    resp = handle(mock_data.get_profile("1"))
    assert "优于" not in resp.data["synthesis"]["narrative"]
    assert "排名" not in resp.data["synthesis"]["narrative"]


# ---------- v3: three-state cell normalization ----------
from app.agents.comparator.engine import FactCell, RowSynthesis, _normalize_cell, _verified_text


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


def test_synthesis_curriculum_focus_never_grants_role_fit(monkeypatch):
    """Only a VERIFIED curriculum_focus cell may feed role_fit (v3 spec 2.1).

    The expectation is derived from the dataset text, not from the engine: NUS's
    curriculum_focus names "Digital Financial Transactions" and NTU's names
    "blockchain", so both earn payments while both cells are verified. Relabelling
    ONLY the NUS cell as synthesis must strip NUS's credit and leave NTU's intact.
    """
    def payments_fit() -> dict[str, float]:
        return {r.program: r.synthesis.score_breakdown["role_fit"]
                for r in compare([TargetRole.payments]).rows}

    before = payments_fit()
    nus_name = next(p for p in before if p.startswith("NUS"))
    ntu_name = next(p for p in before if p.startswith("NTU"))
    assert before[nus_name] == 1.0 and before[ntu_name] == 1.0

    raw = _json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    nus = next(p for p in raw["programs"] if p["program"] == nus_name)
    nus["values"]["curriculum_focus"] = {
        "text": nus["values"]["curriculum_focus"], "kind": "synthesis"}
    monkeypatch.setattr(engine, "_load", lambda: raw)

    after = payments_fit()
    assert after[nus_name] == 0.0, "synthesis curriculum_focus was still scored"
    assert after[ntu_name] == 1.0, "an unrelated verified row lost its evidence"


def test_new_dimension_cells_verified_only_when_sourced():
    """The 4 PDF dimensions carry real provenance where the fact is published.

    career_pathways / industry_orientation restate facts printed on the NUS
    programme page, so they are verified; technical_depth is a qualitative
    judgement and must never claim verified provenance (v3 spec §1.1).
    """
    comp = compare([TargetRole.fintech_pm])
    nus = next(r for r in comp.rows if r.program.startswith("NUS"))
    for dim in ("career_pathways", "industry_orientation"):
        assert nus.facts[dim].kind == "verified", dim
        assert nus.facts[dim].source_url and nus.facts[dim].fetched_at
    for r in comp.rows:
        assert r.facts["technical_depth"].kind == "synthesis", r.program


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
from app.agents.comparator.engine import violates_ranking


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
def test_dataset_has_new_dimensions_and_validates():
    raw = _json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    dims = set(raw["dimensions"])
    assert {"typical_profile", "industry_orientation",
            "technical_depth", "career_pathways"} <= dims
    ok, err = validate_draft(ProgramsDataset, raw)
    assert ok, err


def test_dataset_exercises_all_three_kinds():
    comp = compare([TargetRole.fintech_pm])
    kinds = {c.kind for r in comp.rows for c in r.facts.values()}
    assert kinds == {"verified", "unknown", "synthesis"}
