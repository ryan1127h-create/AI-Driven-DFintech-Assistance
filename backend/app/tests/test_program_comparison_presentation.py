"""The programme comparison tool's S7 (render view, guardrail, renderer,
follow-up, save suggestions) and the handler that sequences the steps —
with the model and the data reads faked."""

from __future__ import annotations

from datetime import date

import pytest
from langchain_core.messages import HumanMessage

from app.domains.specialist.program_comparison.interface import compare
from app.tests.test_program_comparison_tool import PROGRAMS, ROLES, prefetched
from app.tools.specialist.program_comparison import tool
from app.tools.specialist.program_comparison.s1_understanding.schema import ParsedComparisonRequest
from app.tools.specialist.program_comparison.s7_presentation import follow_up, guardrail, renderer
from app.tools.specialist.program_comparison.s7_presentation.payload import money, to_render_view
from app.tools.specialist.program_comparison.s7_presentation.save_suggestions import save_suggestions
from app.tools.turn_context import PreviousTurn, TurnState

TODAY = date(2026, 10, 14)


def _catalogue():
    programs = [dict(p, facts=dict(p["facts"])) for p in PROGRAMS]
    dft, _, hkust, ntu, _ = programs
    dft["fees"] = [{"student_category": "all", "amount": 76409, "currency": "SGD", "basis": "programme",
                    "source_url": "https://dft/fees"}]
    dft["funding"] = [
        {"funding_id": "sg", "name": "Enhanced Rebate", "kind": "rebate", "amount_kind": "percent_tuition",
         "percent": 40, "eligible_categories": ["sg_citizen", "sg_pr"], "source_url": "https://nus/r"},
        {"funding_id": "grtii", "name": "GRTII Scholarship", "kind": "scholarship", "amount_kind": "fixed",
         "amount": 45000, "currency": "SGD", "eligible_categories": None, "bond_required": True,
         "source_url": "https://dft/s"},
    ]
    dft["facts"].update(duration_ft_months=18, gmat_gre_policy="recommended")
    dft["sources"] = {"gmat_gre_policy": [
        {"source_url": "https://dft/faq", "quote": "not mandatory", "role": "primary"},
        {"source_url": "https://dft/adm", "quote": "GMAT 650 and above", "role": "conflicting", "note": "FAQ governs."}]}
    dft["deadlines"] = [{"round_no": 1, "opens_on": date(2026, 10, 1), "closes_on": date(2027, 1, 31),
                         "source_url": "https://dft/app"}]
    hkust["fees"] = [{"student_category": "all", "amount": 405000, "currency": "HKD", "basis": "programme",
                      "source_url": "https://ust/fees"}]
    hkust["facts"].update(duration_ft_months=12)
    ntu["fees"] = [{"student_category": "all", "amount": 68378.75, "currency": "SGD", "basis": "programme",
                    "source_url": "https://ntu/fees"}]
    return programs


def _result(mode="compare", subjects=("hkust_msc_fintech", "ntu_msc_fintech"), applicant=None, **extra):
    return compare({"mode": mode, "today": TODAY, "programs": _catalogue(), "subject_ids": list(subjects),
                    "applicant": applicant or {}, **extra})


UNIVERSITIES = [p["university"] for p in PROGRAMS if p["university"]["university_id"] != "nus"]


# ── render view ───────────────────────────────────────────────────────────

def test_money_keeps_its_currency_and_cents_only_when_present():
    assert (money(76409, "SGD"), money(68378.75, "SGD"), money(45845.4, "SGD")) == (
        "SGD 76,409", "SGD 68,378.75", "SGD 45,845.40")


def test_compare_view_states_differences_from_dft():
    view = to_render_view(_result())
    assert view["msc_dft"]["this_is_msc_dft"] and len(view["compared_with"]) == 2
    diffs = view["differences_from_msc_dft"]
    assert "Tuition: MSc DFT SGD 76,409 vs HKUST MSc(FinTech) HKD 405,000 — different currencies, not converted" in diffs
    assert "Tuition: NTU MSc FinTech costs SGD 8,030.25 less than MSc DFT (SGD 68,378.75 vs SGD 76,409)" in diffs
    assert "Full-time length: HKUST MSc(FinTech) 12 months vs MSc DFT 18 months" in diffs


def test_conflicts_become_caveats():
    [caveat] = to_render_view(_result())["caveats"]
    assert caveat.startswith("NUS MSc DFinTech GMAT/GRE: another official page states this differently")
    assert '"GMAT 650 and above"' in caveat and caveat.endswith("FAQ governs.")


def test_funding_status_never_says_the_user_applied():
    cost = to_render_view(_result(applicant={"residency": "sg_citizen"}))["msc_dft"]["for_you"]["cost"]
    assert cost["after_automatic_reduction"].startswith("SGD 45,845.40 after Enhanced Rebate (40% of tuition")
    [grtii] = cost["may_also_apply"]
    assert "would need a separate application" in grtii and "applied for" not in grtii


def test_asked_which_suits_the_view_lays_out_the_goals_and_the_count():
    view = to_render_view(_result(applicant={"decision_factors": ["duration", "cost"]}, asks_which_suits=True))
    goals = {c["goal"]: c for c in view["your_goals"]["checks"]}
    duration = goals["Programme length (a factor you said matters)"]
    assert duration["by_programme"]["NUS MSc DFinTech"] == "18 months full-time"
    assert "NUS MSc DFinTech" not in duration["ahead"]
    assert goals["Cost for you (a factor you said matters)"]["ahead"] == "not comparable (different currencies)"
    assert set(view["your_goals"]["goals_each_is_ahead_on"]) == {"NUS MSc DFinTech", "HKUST MSc(FinTech)",
                                                                  "NTU MSc FinTech"}
    assert "your_goals" not in to_render_view(_result(applicant={"decision_factors": ["duration"]}))


def test_explore_view_counts_matches_without_dft():
    view = to_render_view(_result("explore", (), conditions={"countries": ["HK"]}))
    assert view["how_many_match"] == 1 and view["msc_dft"]["programme"].startswith("NUS")


def test_detail_view_is_about_one_programme():
    view = to_render_view(_result("detail", ("ntu_msc_fintech",)))
    assert view["programme"]["programme"].startswith("NTU MSc FinTech") and "compared_with" not in view


# ── guardrail ─────────────────────────────────────────────────────────────

VIEW = {"msc_dft": {"programme": "NUS MSc DFinTech", "facts": {"cost": {"tuition": ["SGD 76,409"]},
        "deadlines": ["closes 2027-01-31"]}}, "compared_with": [{"programme": "HKUST MSc(FinTech)",
        "facts": {"cost": {"tuition": ["HKD 405,000"]}}}]}


def test_a_faithful_reply_passes():
    reply = "MSc DFT costs SGD 76,409 and HKUST HKD 405,000; DFT applications close 2027年1月31日."
    assert guardrail.check(reply, VIEW, "", UNIVERSITIES) == []


@pytest.mark.parametrize("reply, problem", [
    ("DFT costs SGD 80,000.", "amounts not in the result"),
    ("HKUST 约 40.5万港币。", "amounts restated in other units"),
    ("DFT costs S$76,409, about SGD 70k after aid.", "amounts restated in other units"),
    ("Applications close in March 2027.", "dates not in the result"),
    ("You might also consider NTU or 南洋理工.", "programmes not in the result"),
    ("综合来看，港科大是更好的选择。", "ranking or verdict wording"),
    ("MSc DFT is better than HKUST for you.", "ranking or verdict wording"),
])
def test_guardrail_catches(reply, problem):
    violations = guardrail.check(reply, VIEW, "", UNIVERSITIES)
    assert any(v.startswith(problem) for v in violations), violations


def test_what_the_user_said_may_be_echoed():
    assert guardrail.check("Yes, HKUST compared with NTU's March 2027 round…", VIEW, "what about NTU in March 2027?",
                           UNIVERSITIES) == []


# ── renderer ──────────────────────────────────────────────────────────────

def test_renderer_retries_once_then_falls_back_to_the_template(monkeypatch):
    drafts = iter(["HKUST is better than DFT.", "Still better than DFT."])
    monkeypatch.setattr(renderer, "render_structured_reply", lambda *a, **k: (next(drafts), ["s"]))
    reply, sources = renderer.render(_result(), UNIVERSITIES, "compare")
    # The deterministic template: the view's facts, nothing invented.
    assert "SGD 76,409" in reply and "HKD 405,000" in reply
    assert "better than" not in reply and sources == ["s"]


def test_renderer_keeps_a_corrected_draft(monkeypatch):
    calls = []

    def fake(view, message, style, **kwargs):
        calls.append(style)
        return ("HKUST is better than DFT." if len(calls) == 1 else "HKUST and NTU are laid out above."), []
    monkeypatch.setattr(renderer, "render_structured_reply", fake)
    assert renderer.render(_result(), UNIVERSITIES, "compare")[0] == "HKUST and NTU are laid out above."
    assert "was rejected" in calls[1]


# ── follow-up and save suggestions ────────────────────────────────────────

def test_compare_records_the_programmes_covered():
    ctx = follow_up.turn_context(_result())
    assert ctx["subjects"] == ["nus_msc_dft", "hkust_msc_fintech", "ntu_msc_fintech"] and ctx["awaiting"] is None
    prev = PreviousTurn("q", "r", contexts=(ctx,))
    assert follow_up.programs_covered(prev) == ctx["subjects"] and follow_up.options_offered(prev) is None


def test_explore_offers_its_matches_to_choose_from():
    ctx = follow_up.turn_context(_result("explore", (), conditions={"countries": ["HK"]}))
    prev = PreviousTurn("q", "r", contexts=(ctx,))
    assert follow_up.options_offered(prev) == [{"key": "hkust_msc_fintech", "label": "HKUST MSc(FinTech)"}]
    assert follow_up.programs_covered(prev) == []


def test_new_competing_programmes_are_offered_for_saving():
    pre = prefetched(facts={"competing_programs": ["NTU FinTech"]})
    pre = type(pre)(**{**pre.__dict__, "profile_read": True})
    parsed = ParsedComparisonRequest(programs=["nus_msc_dft", "ntu_msc_fintech", "hkust_msc_fintech"])
    assert save_suggestions(parsed, pre, "compare") == [
        {"field_key": "competing_programs", "value": ["NTU FinTech", "hkust_msc_fintech"]}]
    assert save_suggestions(parsed, pre, "detail") == []


def test_no_suggestion_without_the_whole_profile():
    parsed = ParsedComparisonRequest(programs=["hkust_msc_fintech"])
    assert save_suggestions(parsed, prefetched(), "compare") == []


# ── the handler ───────────────────────────────────────────────────────────

def test_handler_sequences_the_steps(monkeypatch):
    monkeypatch.setattr(tool, "catalogue", _catalogue)
    monkeypatch.setattr(tool, "role_catalog", lambda: ROLES)
    monkeypatch.setattr(tool.parser, "parse",
                        lambda msg, programs, roles, options: ParsedComparisonRequest(programs=["hkust_msc_fintech"]))
    pre = prefetched(notes=("Profile note.",))
    monkeypatch.setattr(tool, "prefetch", lambda uid: type(pre)(**{**pre.__dict__, "programs": _catalogue()}))
    seen = {}

    def fake_render(result, universities, message, **kwargs):
        seen.update(result=result, universities=universities)
        return "reply", ["https://dft/fees"]
    monkeypatch.setattr(tool.renderer, "render", fake_render)

    answer = tool._handler(TurnState(messages=[HumanMessage("DFT vs 港科大")], user_id="u1"))
    assert answer.text == "reply" and answer.agent_used == "comparison_agent"
    assert seen["result"]["notes"][0] == "Profile note."
    assert "nus" not in {u["university_id"] for u in seen["universities"]}
    assert answer.contexts[0]["subjects"] == ["nus_msc_dft", "hkust_msc_fintech"]


def test_the_tool_skips_evaluation_and_has_a_fallback():
    assert tool.COMPARISON_TOOL.skip_evaluation and tool.COMPARISON_TOOL.input_needs is tool.input_needs
    assert "couldn't" in tool._fallback(TurnState(messages=[], user_id="u1")).text


def test_a_covered_programme_left_out_of_the_reply_is_caught():
    reply = "MSc DFT costs SGD 76,409."  # HKUST, which the view covers, is never named
    assert any(v.startswith("programmes in the result left out of the reply: HKUST")
               for v in guardrail.check(reply, VIEW, "", UNIVERSITIES))
    assert guardrail.check("港科大的学费是 HKD 405,000；MSc DFT 是 SGD 76,409。", VIEW, "", UNIVERSITIES) == []
