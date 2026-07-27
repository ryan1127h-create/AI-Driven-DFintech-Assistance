"""Deterministic tests for #7 navigator (skill derivation + gaps + modules)."""
from agents.navigator.agent import handle
from agents.navigator.engine import derive_user_skills, guide_for_role, pick_primary_role
from common import mock_data
from common.profile import TargetRole


def test_skill_derivation_from_profile():
    p = mock_data.get_profile("1")  # tech=intermediate, fin=basic, banking
    skills = derive_user_skills(p)
    assert "programming" in skills and "data_analytics" in skills
    assert "finance" in skills  # from banking work domain
    assert "risk_modeling" not in skills  # tech not advanced


def test_gap_for_fintech_pm():
    p = mock_data.get_profile("1")
    g = guide_for_role(p, TargetRole.fintech_pm)  # needs product, programming, finance
    assert "product" in g.skill_gaps  # user lacks product
    assert "programming" not in g.skill_gaps  # user has it


def test_modules_come_from_map():
    p = mock_data.get_profile("1")
    g = guide_for_role(p, TargetRole.quant_risk)
    codes = {m["code"] for m in g.recommended_modules}
    assert "DBA5109" in codes  # real NUS module for quant risk


def test_recommended_modules_enriched_from_catalog():
    # Codes referenced by the map are present in the refreshed catalog, so each
    # recommended module should carry authoritative credits + a source link.
    p = mock_data.get_profile("1")
    g = guide_for_role(p, TargetRole.quant_risk)
    for m in g.recommended_modules:
        assert m["verified"] is True
        assert m["credits"] is not None
        assert m["source_url"] and "nusmods.com" in m["source_url"]


def test_pick_role_slot_override():
    p = mock_data.get_profile("1")
    role = pick_primary_role(p, {"target_role": "payments"})
    assert role == TargetRole.payments


def test_pick_role_defaults_to_first_target():
    p = mock_data.get_profile("1")
    assert pick_primary_role(p, {}) == TargetRole.fintech_pm


def test_handle_needs_role_when_none():
    p = mock_data.get_profile("1")
    p.target_roles = []
    resp = handle(p, {})
    assert resp.status == "need_clarification"
    assert "target_roles" in resp.missing_fields


def test_handle_envelope():
    p = mock_data.get_profile("1")
    resp = handle(p, {})
    assert resp.status == "ok"
    assert resp.answer_type == "recommendation"
    assert resp.data["recommended"]
    assert resp.data["selection_source"] in ("llm", "rule")
    assert "graduation_progress" in resp.data and "study_plans" in resp.data
    assert "unrecognized_completed" in resp.data


def test_handle_excludes_completed_and_flags_unknown():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312", "ZZZ000"]
    resp = handle(p, {})
    rec_codes = {m["code"] for m in resp.data["recommended"]}
    assert "BMS5312" not in rec_codes
    assert "BMS5312" in {m["code"] for m in resp.data["already_completed"]}
    assert "ZZZ000" in resp.data["unrecognized_completed"]


# ---------- progress-aware: module_skills loader ----------
from agents.navigator.engine import _load_module_skills, _VALID_SKILL_TAGS


def test_module_skills_loads_and_tags_are_valid():
    m = _load_module_skills()
    assert m.get("BMS5312") == ["product", "finance"]
    for code, tags in m.items():
        assert set(tags) <= _VALID_SKILL_TAGS, code


# ---------- D: completed -> skills ; E: unrecognized codes ----------
from agents.navigator.engine import skills_from_completed, unrecognized_completed


def test_skills_from_completed_aggregates_valid_tags():
    s = skills_from_completed(["BMS5312", "FT5005"])
    assert {"product", "finance", "ai_ml", "programming"} <= s


def test_skills_from_completed_unknown_code_contributes_nothing():
    assert skills_from_completed(["NOPE999"]) == set()


def test_skills_from_completed_empty():
    assert skills_from_completed([]) == set()


def test_unrecognized_completed_flags_unknown_codes():
    out = unrecognized_completed(["BMS5312", "ZZZ000"])
    assert "ZZZ000" in out and "BMS5312" not in out


def test_unrecognized_completed_empty():
    assert unrecognized_completed([]) == []


# ---------- A + D: guide_for_role is completed-aware ----------
def test_guide_marks_completed_modules():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312"]  # a fintech_pm recommended module
    g = guide_for_role(p, TargetRole.fintech_pm)
    done = {m["code"] for m in g.recommended_modules if m.get("completed")}
    assert "BMS5312" in done
    assert "BMS5312" in {m["code"] for m in g.already_completed}
    assert "BMS5312" not in {m["code"] for m in g.recommended_remaining}


def test_guide_completed_shrinks_gap():
    p = mock_data.get_profile("1")
    assert "product" in guide_for_role(p, TargetRole.fintech_pm).skill_gaps
    p.completed_modules = ["BMS5312"]  # product, finance
    g = guide_for_role(p, TargetRole.fintech_pm)
    assert "product" not in g.skill_gaps
    assert "product" in g.skills_from_courses


# ---------- F: candidate pool + deterministic ranking ----------
from agents.navigator.engine import build_candidates, rank_candidates


def test_candidates_exclude_completed_and_annotate():
    p = mock_data.get_profile("1")
    p.completed_modules = ["BMS5312"]
    cands = build_candidates(p, TargetRole.fintech_pm)
    codes = {c["code"] for c in cands}
    assert "BMS5312" not in codes
    assert cands and all("closes_gaps" in c and "skills" in c for c in cands)


def test_candidates_include_gap_addressing_modules():
    p = mock_data.get_profile("1")
    codes = {c["code"] for c in build_candidates(p, TargetRole.fintech_pm)}
    assert {"FT5001", "IS5009"} & codes


def test_rank_prioritises_more_gaps_closed():
    p = mock_data.get_profile("1")
    cands = build_candidates(p, TargetRole.fintech_pm)
    ranked = rank_candidates(cands)
    closes = [len(c["closes_gaps"]) for c in ranked]
    assert closes == sorted(closes, reverse=True)


# ---------- F: LLM-constrained selection with validation ----------
from agents.navigator import engine as nav_engine
from agents.navigator.engine import select_modules


def _cands(p=None):
    p = p or mock_data.get_profile("1")
    return build_candidates(p, TargetRole.fintech_pm)


def test_select_falls_back_to_rule_when_llm_off(monkeypatch):
    monkeypatch.setattr(nav_engine.llm, "available", lambda: False)
    cands = _cands()
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "rule"
    assert 1 <= len(selected) <= 3
    assert selected == rank_candidates(cands)[:3]


def test_select_llm_keeps_only_valid_codes(monkeypatch):
    cands = _cands()
    valid_code = cands[0]["code"]
    monkeypatch.setattr(nav_engine.llm, "available", lambda: True)
    monkeypatch.setattr(nav_engine.llm, "explain",
                        lambda *a, **k: f"SELECTED: {valid_code}, FAKE999\n因为它能补缺口。")
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "llm"
    codes = [c["code"] for c in selected]
    assert valid_code in codes and "FAKE999" not in codes
    assert "SELECTED" not in rationale          # machine line stripped from prose


def test_select_all_invalid_falls_back(monkeypatch):
    cands = _cands()
    monkeypatch.setattr(nav_engine.llm, "available", lambda: True)
    monkeypatch.setattr(nav_engine.llm, "explain", lambda *a, **k: "SELECTED: FAKE1, FAKE2")
    selected, rationale, source = select_modules(cands, ["product"], n=3)
    assert source == "rule"


# ---------- C: career view + routing ----------
from agents.navigator.agent import career


def test_career_focuses_on_skills_not_scheduling():
    p = mock_data.get_profile("1")
    resp = career(p, {})
    assert resp.status == "ok"
    assert "required_skills" in resp.data and "gap_closing_modules" in resp.data
    assert "study_plans" not in resp.data


def test_supervisor_routes_career_path():
    from supervisor import route
    p = mock_data.get_profile("1")
    resp = route("recommend_career_path", p, {})
    assert resp.status == "ok"
    assert "gap_closing_modules" in resp.data


# ---------- consent: opt-out must not send raw gaps to the external LLM ----------
def test_optout_does_not_leak_gaps_to_llm(monkeypatch):
    from agents.navigator import engine as nav_engine
    prompts: list[str] = []
    monkeypatch.setattr(nav_engine.llm, "available", lambda: True)

    def _spy(system, user, fallback):
        prompts.append(user)
        return "SELECTED: FT5001"

    monkeypatch.setattr(nav_engine.llm, "explain", _spy)
    p = mock_data.get_profile("1")  # fintech_pm gap includes 'product'

    # opt-out: selection uses rule; raw gap id never reaches any LLM prompt
    p.consent_flags.personalization = False
    resp = handle(p, {"target_role": "fintech_pm"})
    assert resp.data["selection_source"] == "rule"
    assert resp.data["skill_gaps"] == []
    assert all("product" not in pr for pr in prompts)

    # opt-in: the gap DOES reach the LLM selection prompt (gating is real, not a no-op)
    prompts.clear()
    p.consent_flags.personalization = True
    handle(p, {"target_role": "fintech_pm"})
    assert any("product" in pr for pr in prompts)
