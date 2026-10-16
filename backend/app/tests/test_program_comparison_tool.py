"""The programme comparison tool's S1 (parser), S2 (name resolution,
builder, prefetch) and gate — with the model and the data reads faked."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.domains.specialist.program_comparison.contracts import ComparisonInput
from app.tools.specialist.program_comparison import gate
from app.tools.specialist.program_comparison.s1_understanding import parser
from app.tools.specialist.program_comparison.s1_understanding.schema import ParsedComparisonRequest
from app.tools.specialist.program_comparison.s2_assembly import prefetch as prefetch_module
from app.tools.specialist.program_comparison.s2_assembly import programs as program_names
from app.tools.specialist.program_comparison.s2_assembly.builder import build_report
from app.tools.specialist.program_comparison.s2_assembly.prefetched import Prefetched
from app.tools.turn_context import TurnState

TODAY = date(2026, 10, 14)


def _program(pid, uni, short, aliases=(), uni_aliases=(), is_target=False, category="fintech", country="SG"):
    return {
        "program_id": pid, "name": f"Master of {pid}", "short_name": short, "degree_type": "MSc",
        "category": category, "is_target": is_target, "aliases": list(aliases),
        "official_url": f"https://{pid}.edu", "intake_year": 2027,
        "university": {"university_id": uni, "name": uni.upper() + " University", "short_name": uni.upper(),
                       "aliases": list(uni_aliases), "city": "C", "country_code": country, "country_name": country},
        "facts": {"study_modes": ["full_time"]}, "sources": {}, "fees": [], "deadlines": [], "funding": [],
        "curriculum": [],
    }


PROGRAMS = [
    _program("nus_msc_dft", "nus", "MSc DFinTech", ["MSc DFT", "数字金融科技"], ["NUS", "国大"], is_target=True),
    _program("nus_msc_ba", "nus", "MSBA", ["MSBA"], ["NUS"], category="business_analytics"),
    _program("hkust_msc_fintech", "hkust", "MSc(FinTech)", ["HKUST FinTech"], ["HKUST", "港科大"], country="HK"),
    _program("ntu_msc_fintech", "ntu", "MSc FinTech", ["NTU FinTech"], ["NTU", "南洋理工"]),
    _program("ucl_msc_fintech", "ucl", "MSc FinTech", [], ["UCL"], country="GB"),
]
ROLES = [{"tag": "quantitative_finance", "name": "Quantitative Finance", "name_zh": "量化金融",
          "required_skills": ["programming", "finance", "risk_modeling", "data_analytics"]}]


def prefetched(facts=None, role_facts=None, notes=()):
    return Prefetched(programs=PROGRAMS, facts=facts or {}, role_facts=role_facts or {}, role_catalog=ROLES,
                      notes=tuple(notes))


def build(parsed=None, mode_hint=None, hints=(), previous=(), **pre):
    built = build_report(prefetched(**pre), parsed or ParsedComparisonRequest(), mode_hint, list(hints),
                         TODAY, "u1", previous)
    ComparisonInput.model_validate(built.report)  # every report the builder makes is valid
    return built


# ── S1 parser ─────────────────────────────────────────────────────────────

def test_parser_keeps_only_catalogue_ids_and_known_roles(monkeypatch):
    reply = {"mode": "compare", "programs": ["nus_msc_dft", "hkust_msc_fintech", "made_up"],
             "dimensions": ["cost", "vibes"], "countries": ["hk"], "role": "astronaut", "intake_year": 2028}
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: json.dumps(reply))
    p = parser.parse("DFT 和港科大比怎么样", PROGRAMS, ROLES)
    assert p.programs == ["nus_msc_dft", "hkust_msc_fintech"]
    assert (p.dimensions, p.countries, p.role, p.intake_year) == (["cost"], ["HK"], None, 2028)


def test_parser_shows_the_catalogue_and_previous_options(monkeypatch):
    seen = {}
    monkeypatch.setattr(parser.llm, "complete", lambda prompt, msg, **k: seen.setdefault("p", prompt) and "{}")
    parser.parse("the second one", PROGRAMS, ROLES, options=[{"key": "ntu_msc_fintech", "label": "NTU MSc FinTech"}])
    assert "港科大" in seen["p"]
    assert "1. NTU MSc FinTech (ntu_msc_fintech)" in seen["p"]


def test_parser_failure_is_marked(monkeypatch):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: "not json")
    assert parser.parse("compare", PROGRAMS, ROLES).parse_failed


def test_empty_message_skips_the_model(monkeypatch):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: pytest.fail("called"))
    assert parser.parse("  ", PROGRAMS, ROLES) == ParsedComparisonRequest()


# ── name resolution ───────────────────────────────────────────────────────

def test_names_resolve_by_programme_or_single_programme_university():
    ids, unmatched = program_names.resolve(["港科大", "NTU FinTech", "ntu", "NUS", "Oxford"], PROGRAMS)
    assert ids == ["hkust_msc_fintech", "ntu_msc_fintech"]
    assert unmatched == ["NUS", "Oxford"]  # NUS has two programmes: ambiguous


# ── builder ───────────────────────────────────────────────────────────────

def test_named_programmes_are_compared_with_dft():
    b = build(ParsedComparisonRequest(programs=["nus_msc_dft", "hkust_msc_fintech"]))
    assert (b.report["mode"], b.report["subject_ids"]) == ("compare", ["hkust_msc_fintech"])


def test_classifier_hints_stand_in_when_parsing_failed():
    b = build(ParsedComparisonRequest(parse_failed=True), hints=["NTU", "Oxford"])
    assert b.report["subject_ids"] == ["ntu_msc_fintech"]
    assert any("Oxford" in n for n in b.notes) and any("couldn't be fully made out" in n for n in b.notes)


def test_only_dft_named_is_a_detail_of_dft():
    b = build(ParsedComparisonRequest(programs=["nus_msc_dft"]))
    assert (b.report["mode"], b.report["subject_ids"]) == ("detail", ["nus_msc_dft"])


def test_detail_with_several_programmes_compares():
    b = build(ParsedComparisonRequest(mode="detail", programs=["ntu_msc_fintech", "ucl_msc_fintech"]))
    assert b.report["mode"] == "compare" and b.report["subject_ids"] == ["ntu_msc_fintech", "ucl_msc_fintech"]


def test_detail_without_a_name_uses_the_previous_single_programme():
    b = build(ParsedComparisonRequest(mode="detail", dimensions=["deadlines"]), previous=["ntu_msc_fintech"])
    assert b.report["subject_ids"] == ["ntu_msc_fintech"]


def test_compare_without_names_reuses_the_previous_comparison():
    b = build(ParsedComparisonRequest(mode="compare", dimensions=["cost"]),
              previous=["nus_msc_dft", "hkust_msc_fintech"])
    assert b.report["subject_ids"] == ["hkust_msc_fintech"] and b.fallback is None


def test_compare_without_names_uses_the_profiles_competing_programmes():
    b = build(ParsedComparisonRequest(mode="compare"), facts={"competing_programs": ["NTU FinTech", "Elsewhere"]})
    assert b.report["subject_ids"] == ["ntu_msc_fintech"]


def test_nothing_to_compare_explores_fintech_programmes():
    b = build(ParsedComparisonRequest(mode="compare"))
    assert b.fallback == "explore_instead_of_compare"
    assert (b.report["mode"], b.report["conditions"]) == ("explore", {"categories": ["fintech"]})
    assert any("No programme to compare" in n for n in b.notes)


def test_an_unknown_programme_says_what_is_covered_instead():
    b = build(ParsedComparisonRequest(mode="compare", programs=["nus_msc_dft"], unmatched_programs=["Oxford"]))
    assert b.fallback and len(b.notes) == 1 and b.notes[0].startswith("Oxford isn't in the comparison data, so")


def test_at_most_three_programmes_are_compared():
    ids = ["nus_msc_ba", "hkust_msc_fintech", "ntu_msc_fintech", "ucl_msc_fintech"]
    b = build(ParsedComparisonRequest(programs=ids))
    assert b.report["subject_ids"] == ids[:3] and any("Only three" in n for n in b.notes)


def test_conditions_alone_explore():
    b = build(ParsedComparisonRequest(countries=["HK"], study_mode="part_time"))
    assert b.report["mode"] == "explore"
    assert b.report["conditions"] == {"countries": ["HK"], "study_mode": "part_time"}


def test_applicant_comes_from_the_profile_and_the_message():
    facts = {"residency_category": "sg_pr", "is_nus_alumnus": "yes", "english_medium_degree": False,
             "admission_tests": [{"key": "IELTS", "score": 7, "test_date": "2025-05-01"}, {"key": "SAT", "score": 1}],
             "total_work_years": "3-5", "decision_factors": ["cost"], "intake_term": "AY2027/28 Sem1"}
    a = build(ParsedComparisonRequest(programs=["ntu_msc_fintech"], intake_year=2028), facts=facts,
              role_facts={"main_target_role": "quantitative_finance"}).report["applicant"]
    assert a["residency"] == "sg_pr" and "is_nus_alumnus" not in a  # not a bool: dropped
    assert a["tests"] == [{"key": "IELTS", "score": 7, "test_date": "2025-05-01"}]
    assert a["intake_year"] == 2028  # the message beats the profile
    assert a["target_role"] == "Quantitative Finance" and "risk_modeling" in a["target_skills"]


def test_a_role_named_in_the_message_needs_no_profile():
    a = build(ParsedComparisonRequest(programs=["ntu_msc_fintech"], role="quantitative_finance")).report["applicant"]
    assert a["target_role"] == "Quantitative Finance"


# ── gate ──────────────────────────────────────────────────────────────────

def _state():
    return TurnState(messages=[], user_id="u1")


def test_gate_never_blocks_and_asks_nothing_without_consent(monkeypatch):
    monkeypatch.setattr(gate, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    assert gate.input_needs(_state()) == ()


def test_gate_offers_residency_and_factors_under_the_answer(monkeypatch):
    monkeypatch.setattr(gate, "missing_purpose_consent", lambda uid, purpose: None)
    monkeypatch.setattr(gate, "get_profile_for_purpose", lambda uid, purpose: {"decision_factors": ["cost"]})
    monkeypatch.setattr("app.tools.input_needs.missing_purpose_consent", lambda uid, purpose: None)
    needs = gate.input_needs(_state())
    assert [(n.field_key, n.level) for n in needs] == [("residency_category", "supplementary")]


# ── prefetch ──────────────────────────────────────────────────────────────

def test_prefetch_runs_unpersonalised_when_the_profile_fails(monkeypatch):
    def broken(uid, purpose):
        raise RuntimeError("db down")
    monkeypatch.setattr(prefetch_module, "list_programs", lambda: PROGRAMS)
    monkeypatch.setattr(prefetch_module, "list_role_tags", lambda: [])
    monkeypatch.setattr(prefetch_module, "get_profile_for_purpose", broken)
    monkeypatch.setattr(prefetch_module, "missing_purpose_consent", lambda uid, purpose: None)
    p = prefetch_module.prefetch("u1")
    assert p.facts == {} and p.target_id == "nus_msc_dft"
    assert any("couldn't be read" in n for n in p.notes)


def test_prefetch_fails_without_the_catalogue(monkeypatch):
    def broken():
        raise RuntimeError("catalogue down")
    monkeypatch.setattr(prefetch_module, "list_programs", broken)
    monkeypatch.setattr(prefetch_module, "list_role_tags", lambda: [])
    with pytest.raises(RuntimeError):
        prefetch_module.prefetch(None)


def test_prefetch_notes_consent_off(monkeypatch):
    monkeypatch.setattr(prefetch_module, "list_programs", lambda: PROGRAMS)
    monkeypatch.setattr(prefetch_module, "list_role_tags", lambda: [])
    monkeypatch.setattr(prefetch_module, "get_profile_for_purpose", lambda uid, purpose: {})
    monkeypatch.setattr(prefetch_module, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    assert any("turned off" in n for n in prefetch_module.prefetch("u1").notes)
