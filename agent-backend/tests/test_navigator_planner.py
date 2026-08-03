"""Deterministic tests for #7 Navigator v2 study-path planner (no LLM)."""
import pytest

from app.agents.navigator import planner as nav_planner
from app.agents.navigator.agent import handle
from app.agents.navigator.planner import (
    PlanInfeasibleError,
    base_code,
    build_study_plan,
    graduation_progress,
    prereq_satisfied,
    prereq_warnings,
    what_if_pathways,
)
from common import mock_data


def _stub_catalog(monkeypatch, modules: list[dict]) -> None:
    """Replace the real catalog so constraint conflicts can be constructed."""
    monkeypatch.setattr(nav_planner, "_load_catalog", lambda: {m["code"]: m for m in modules})


def _module(code: str, credits: int = 4, semesters=(1, 2), prereq_tree=None) -> dict:
    return {"code": code, "name": code, "credits": credits,
            "semesters": list(semesters), "prereq_tree": prereq_tree,
            "workload_hours": credits * 2.5}


# ---------- prereq tree evaluation ----------
def test_base_code_strips_decorations():
    assert base_code("ACC1701%:D") == "ACC1701"
    assert base_code("BMF5324") == "BMF5324"


def test_prereq_none_satisfied():
    assert prereq_satisfied(None, set()) == (True, [])


def test_prereq_and_requires_all():
    tree = {"and": ["BMF5324", "BMF5332"]}
    ok, missing = prereq_satisfied(tree, {"BMF5324"})
    assert not ok and missing == ["BMF5332"]
    assert prereq_satisfied(tree, {"BMF5324", "BMF5332"})[0]


def test_prereq_or_requires_any():
    tree = {"or": ["A:D", "B:D"]}
    assert prereq_satisfied(tree, {"B"})[0] is True
    ok, missing = prereq_satisfied(tree, set())
    assert not ok and set(missing) == {"A", "B"}


def test_prereq_warnings_uses_catalog():
    # BMF5360 has prereqTree {and:[BMF5324, BMF5332]} in the real catalog.
    ws = prereq_warnings(["BMF5360"], completed=[])
    assert ws[0].code == "BMF5360" and not ws[0].satisfied
    assert "BMF5324" in ws[0].missing


# ---------- graduation progress ----------
def test_graduation_progress_math():
    p = graduation_progress(completed=["BMD5301"], recommended_codes=["BMS5312", "BMF5358"])
    assert p["required"] == 52
    assert p["coursework_required"] == 40
    assert p["capstone_required"] == 12
    assert p["completed_credits"] == 4
    assert p["planned_credits"] == 8
    assert p["remaining"] == 52 - 4 - 8


# ---------- study plan / pathways ----------
def test_full_time_respects_credit_cap():
    codes = ["BMS5312", "BMD5301", "FT5001", "BT5153", "DBA5107"]
    plan = build_study_plan(codes, "full_time")
    assert all(t["credits"] <= 20 for t in plan["semesters"])


def test_part_time_smaller_cap_more_terms():
    codes = ["BMS5312", "BMD5301", "FT5001", "BT5153"]
    ft = build_study_plan(codes, "full_time")
    pt = build_study_plan(codes, "part_time")
    assert all(t["credits"] <= 12 for t in pt["semesters"])
    assert pt["num_terms"] >= ft["num_terms"]


def test_study_plan_respects_offered_semester():
    # FT5005 is sourced "Semester 1 - No | Semester 2 - Yes"
    # (data/dft_knowledge_base.txt) -> must land in a Sem 2 term.
    plan = build_study_plan(["FT5005"], "full_time")
    ft = next(t for t in plan["semesters"] for m in t["modules"] if m["code"] == "FT5005")
    assert ft["semester"] == 2


def test_what_if_returns_both_pathways():
    plans, error = what_if_pathways(["BMS5312", "BT5153"])
    assert set(plans) == {"full_time", "part_time"}
    assert error is None


def test_one_infeasible_pathway_keeps_the_other_pathways_plan(monkeypatch):
    # A 16-Unit module fits the 20-Unit full-time cap but never the 12-Unit
    # part-time cap: the part-time failure must not discard the full-time plan.
    _stub_catalog(monkeypatch, [_module("XX9002", credits=16)])
    plans, error = what_if_pathways(["XX9002"])
    assert set(plans) == {"full_time"}
    assert plans["full_time"]["semesters"][0]["credits"] == 16
    assert error and "part_time" in error and "full_time" not in error


# ---------- agent integration ----------
def test_handle_includes_planning_fields():
    p = mock_data.get_profile("1")  # completed_modules=["BMD5301"]
    resp = handle(p, {"target_role": "data_analytics"})
    d = resp.data
    assert "graduation_progress" in d and d["graduation_progress"]["completed_credits"] == 4
    assert "study_plans" in d and set(d["study_plans"]) == {"full_time", "part_time"}
    # BMF5360 prereq unmet -> warning surfaced
    assert any(w["code"] == "BMF5360" for w in d["prereq_warnings"])


def test_handle_reports_a_valid_plan_for_a_real_profile():
    p = mock_data.get_profile("1")
    resp = handle(p, {"target_role": "data_analytics"})
    assert resp.data["study_plan_error"] is None
    for plan in resp.data["study_plans"].values():
        assert all(t["modules"] for t in plan["semesters"])
        assert all(t["credits"] <= plan["term_credit_cap"] for t in plan["semesters"])


def test_handle_surfaces_plan_failure_instead_of_raising(monkeypatch):
    # A 2-Unit cap cannot hold any real 4-Unit module -> infeasible for every term.
    monkeypatch.setattr(nav_planner, "_CREDIT_CAP", {"full_time": 2, "part_time": 2})
    p = mock_data.get_profile("1")
    resp = handle(p, {"target_role": "data_analytics"})
    assert resp.status == "ok"
    assert resp.data["study_plans"] == {}
    assert "2-credit" in resp.data["study_plan_error"]
    assert "could not build a valid semester timetable" in resp.speakable


def test_handle_keeps_the_feasible_pathway_when_the_other_is_infeasible(monkeypatch):
    # Only part-time is impossible (a 2-Unit cap holds no 4-Unit module); the
    # full-time plan is valid and must still reach the user.
    monkeypatch.setattr(nav_planner, "_CREDIT_CAP", {"full_time": 20, "part_time": 2})
    p = mock_data.get_profile("1")
    resp = handle(p, {"target_role": "data_analytics"})
    assert set(resp.data["study_plans"]) == {"full_time"}
    assert resp.data["study_plans"]["full_time"]["semesters"]
    assert "part_time" in resp.data["study_plan_error"]
    # The spoken note must name the failed pathway, not imply every pathway failed.
    assert "part-time pathway" in resp.speakable
    assert "full-time" not in resp.speakable


# ---------- B: progress never double-counts completed ----------
def test_graduation_progress_excludes_completed_from_planned():
    completed = ["BMS5312"]
    prog = graduation_progress(completed, ["BMS5312", "FT5001"])
    only_remaining = graduation_progress(completed, ["FT5001"])
    assert prog["planned_credits"] == only_remaining["planned_credits"]


# ---------- 1a: prerequisites constrain the term order ----------
def test_module_never_precedes_its_prerequisite():
    # FT5011 ("Deep Learning for Finance") has prereq_tree "FT5005" in the catalog.
    plan = build_study_plan(["FT5011", "FT5005"], "full_time")
    order = [m["code"] for t in plan["semesters"] for m in t["modules"]]
    assert order.index("FT5005") < order.index("FT5011")
    terms = {m["code"]: t["term"] for t in plan["semesters"] for m in t["modules"]}
    assert terms["FT5005"] != terms["FT5011"]  # not merely earlier in the same term


def test_prerequisite_order_holds_for_both_input_orders():
    for codes in (["FT5011", "FT5005"], ["FT5005", "FT5011"]):
        plan = build_study_plan(codes, "part_time")
        order = [m["code"] for t in plan["semesters"] for m in t["modules"]]
        assert order == ["FT5005", "FT5011"], codes


def test_completed_prerequisite_frees_the_first_term(monkeypatch):
    _stub_catalog(monkeypatch, [_module("AA1000"), _module("BB2000", prereq_tree="AA1000")])
    plan = build_study_plan(["BB2000"], "full_time", completed=["aa1000"])
    assert [t["term"] for t in plan["semesters"]] == ["Year 1 · Sem 1"]


def test_partial_and_prereq_still_orders_the_in_plan_branch(monkeypatch):
    # BB2000 needs AA1000 (in the plan) AND ZZ9999 (not in the catalog at all).
    # The unsatisfiable branch is an unmet prerequisite -- prereq_warnings' job --
    # and must not cancel the ordering constraint from the branch being scheduled.
    _stub_catalog(monkeypatch, [
        _module("AA1000"),
        _module("BB2000", prereq_tree={"and": ["AA1000", "ZZ9999"]}),
    ])
    plan = build_study_plan(["BB2000", "AA1000"], "full_time")
    order = [m["code"] for t in plan["semesters"] for m in t["modules"]]
    assert order == ["AA1000", "BB2000"]
    terms = {m["code"]: t["term"] for t in plan["semesters"] for m in t["modules"]}
    assert terms["AA1000"] != terms["BB2000"]  # strictly earlier term, not same term


def test_partly_satisfiable_prereq_neither_loses_nor_swallows_the_failure(monkeypatch):
    """An unsatisfiable `and` branch must stay visible in BOTH directions.

    DD4000 needs AA1000 (in the plan) AND ZZ9999 (nowhere): the conjunction cannot
    be met, yet AA1000 must still be ordered first -- dropping the whole conjunction
    loses that.  CC3000 needs (AA1000 AND ZZ9999) OR BB2000: only the BB2000 branch
    is satisfiable, so BB2000 -- not AA1000 -- is the ordering constraint.  Treating
    the unsatisfiable `and` as satisfiable makes the `or` pick AA1000 and schedules
    CC3000 without BB2000 behind it.  EE5000 pins the same rule one level down: an
    `or` whose every branch is unsatisfiable must report failure, or the enclosing
    `or` adopts it as the cheapest alternative and loses the AA1000 constraint.
    """
    _stub_catalog(monkeypatch, [
        _module("AA1000", semesters=(1,)),
        _module("BB2000", semesters=(2,)),
        _module("CC3000", prereq_tree={"or": [{"and": ["AA1000", "ZZ9999"]}, "BB2000"]}),
        _module("DD4000", prereq_tree={"and": ["AA1000", "ZZ9999"]}),
        _module("EE5000", prereq_tree={"or": [{"or": ["ZZ8888", "ZZ9999"]}, "AA1000"]}),
    ])
    plan = build_study_plan(["CC3000", "DD4000", "EE5000", "AA1000", "BB2000"],
                           "full_time")
    slots = [t["term"] for t in plan["semesters"]]
    at = {m["code"]: t["term"] for t in plan["semesters"] for m in t["modules"]}
    assert slots.index(at["AA1000"]) < slots.index(at["DD4000"])
    assert slots.index(at["BB2000"]) < slots.index(at["CC3000"])
    assert slots.index(at["AA1000"]) < slots.index(at["EE5000"])


def test_wholly_unsatisfiable_prereq_does_not_block_scheduling(monkeypatch):
    # Nothing in the plan can satisfy the tree, so there is no ordering constraint
    # to honour: the module is still laid out rather than declared infeasible
    # (the unmet prerequisite is reported separately by prereq_warnings).
    _stub_catalog(monkeypatch, [_module("BB2000", prereq_tree={"and": ["ZZ9999"]})])
    plan = build_study_plan(["BB2000"], "full_time")
    assert [m["code"] for t in plan["semesters"] for m in t["modules"]] == ["BB2000"]


def test_cyclic_prerequisites_fail_loudly(monkeypatch):
    _stub_catalog(monkeypatch, [_module("AA1000", prereq_tree="BB2000"),
                                _module("BB2000", prereq_tree="AA1000")])
    with pytest.raises(PlanInfeasibleError) as err:
        build_study_plan(["AA1000", "BB2000"], "full_time")
    assert "prerequisite" in str(err.value) and "AA1000" in str(err.value)


# ---------- 1b: no empty term before a non-empty one ----------
def test_no_empty_terms_emitted():
    # FT5005 is sourced Sem 2 only, so the Sem 1 slot must be skipped, not emitted empty.
    plan = build_study_plan(["FT5005"], "full_time")
    assert plan["num_terms"] == len(plan["semesters"]) == 1
    assert all(t["modules"] for t in plan["semesters"])
    assert plan["semesters"][0]["semester"] == 2


def test_no_empty_term_between_two_populated_terms():
    plan = build_study_plan(["FT5011", "FT5005"], "full_time")  # both Sem 2 only
    assert all(t["modules"] for t in plan["semesters"])
    assert [t["semester"] for t in plan["semesters"]] == [2, 2]


# ---------- 1c: per-term credit bounds ----------
def test_min_credits_balances_terms_instead_of_leaving_a_stub():
    # 6 x 4 Units = 24 > the 20-Unit cap.  Every one of these modules is offered in
    # BOTH semesters, so the offering pattern forces nothing: only _term_target can
    # produce 12 / 12 here.  Greedy filling to the cap gives 20 / 4, leaving a stub
    # term below the 12-Unit full-time minimum.
    codes = ["CS5242", "CS5344", "IT5001", "IT5004", "IT5005", "IT5008"]
    plan = build_study_plan(codes, "full_time")
    assert [t["credits"] for t in plan["semesters"]] == [12, 12]
    assert plan["min_credits_met"] is True
    assert plan["below_min_terms"] == []
    assert all(t["credits"] <= plan["term_credit_cap"] for t in plan["semesters"])


def test_min_credits_is_what_balances_the_terms_not_the_offering_pattern(monkeypatch):
    # Guard for the test above: with the minimum switched off, the same flexible
    # modules greedily fill to the cap and leave the 4-Unit stub.
    codes = ["CS5242", "CS5344", "IT5001", "IT5004", "IT5005", "IT5008"]
    monkeypatch.setattr(nav_planner, "_CREDIT_MIN", {"full_time": 0, "part_time": 0})
    plan = build_study_plan(codes, "full_time")
    assert [t["credits"] for t in plan["semesters"]] == [20, 4]


def test_short_selection_reports_min_shortfall_without_inventing_credits():
    plan = build_study_plan(["BMS5312"], "full_time")  # 4 Units < 12-Unit minimum
    assert plan["min_credits_met"] is False
    assert plan["below_min_terms"] == [plan["semesters"][0]["term"]]
    assert plan["semesters"][0]["below_min_credits"] is True


def test_module_larger_than_the_term_cap_fails_loudly(monkeypatch):
    _stub_catalog(monkeypatch, [_module("XX9000", credits=24)])
    with pytest.raises(PlanInfeasibleError) as err:
        build_study_plan(["XX9000"], "full_time")
    assert "20-credit" in str(err.value) and "XX9000" in str(err.value)


def test_offering_that_never_fits_fails_loudly(monkeypatch):
    # Semester 9 does not exist among the planner's teaching terms.
    _stub_catalog(monkeypatch, [_module("XX9001", semesters=(9,))])
    with pytest.raises(PlanInfeasibleError) as err:
        build_study_plan(["XX9001"], "full_time")
    assert "XX9001" in str(err.value) and "never fitted" in str(err.value)


# ---------- 2: unknown codes must not inflate progress ----------
def test_unknown_completed_code_adds_no_credits():
    known_only = graduation_progress(["BMD5301"], [])
    with_unknown = graduation_progress(["BMD5301", "ZZZ000"], [])
    assert with_unknown["completed_credits"] == known_only["completed_credits"] == 4
    assert with_unknown["unrecognized_completed"] == ["ZZZ000"]
    assert with_unknown["remaining"] == known_only["remaining"]


def test_repeated_code_is_counted_once():
    # The same 4-Unit module twice (any casing) is still 4 Units of progress.
    once = graduation_progress(["BMD5301"], [])
    twice = graduation_progress(["BMD5301", "bmd5301"], [])
    assert twice["completed_credits"] == once["completed_credits"] == 4
    assert twice["remaining"] == once["remaining"]
    assert graduation_progress([], ["BMS5312", "bms5312"])["planned_credits"] == 4


def test_unknown_recommended_code_adds_no_planned_credits():
    prog = graduation_progress([], ["BMS5312", "ZZZ000"])
    assert prog["planned_credits"] == 4


def test_unknown_code_is_reported_not_scheduled():
    plan = build_study_plan(["BMS5312", "ZZZ000"], "full_time")
    scheduled = {m["code"] for t in plan["semesters"] for m in t["modules"]}
    assert scheduled == {"BMS5312"}
    assert plan["unrecognized"] == ["ZZZ000"]


# ---------- 3: case-insensitive module lookup ----------
def test_lowercase_codes_resolve_in_progress():
    assert graduation_progress(["bmd5301"], ["bms5312"])["completed_credits"] == 4
    assert graduation_progress(["bmd5301"], ["bms5312"])["planned_credits"] == 4
    assert graduation_progress([" bmd5301 "], [])["unrecognized_completed"] == []


def test_lowercase_code_finds_prereq_tree():
    ws = prereq_warnings(["bmf5360"], completed=[])
    assert not ws[0].satisfied and "BMF5324" in ws[0].missing


def test_lowercase_completed_satisfies_prereq():
    ws = prereq_warnings(["FT5011"], completed=["ft5005"])
    assert ws[0].satisfied


def test_lowercase_code_is_scheduled_and_priced():
    plan = build_study_plan(["bt5153"], "full_time")
    assert plan["unrecognized"] == []
    assert plan["semesters"][0]["modules"][0] == {
        "code": "BT5153",
        "name": "Applied Machine Learning for Business Analytics",
        "credits": 4,
    }


# ---------- 4: workload provenance + capstone module ----------
def test_no_overload_verdict_is_published_while_workload_is_unsourced():
    # workload_hours is credits * 2.5 (an estimate) and the repo sources no
    # weekly-hours limit, so the planner must publish provenance, not a verdict.
    plan = build_study_plan(["FT5001", "FT5002", "FT5009"], "part_time")
    assert plan["workload_sourced"] is False
    assert plan["workload_note"] and "estimate" in plan["workload_note"]
    assert "overload_basis" not in plan
    assert all("overload" not in t for t in plan["semesters"])


def test_at_credit_cap_marks_the_sourced_per_term_maximum():
    # 5 x 4 Units = 20, the sourced full-time maximum, and all five are offered in
    # both semesters so they land in one term.
    heavy = build_study_plan(["CS5242", "CS5344", "IT5001", "IT5004", "IT5005"],
                             "full_time")
    assert [t["credits"] for t in heavy["semesters"]] == [20]
    assert heavy["semesters"][0]["at_credit_cap"] is True
    # A single 4-Unit module is not at the maximum.
    light = build_study_plan(["CS5242"], "full_time")
    assert light["semesters"][0]["at_credit_cap"] is False


def test_capstone_module_is_in_the_catalog():
    prog = graduation_progress(["FT5007"], [])
    assert prog["unrecognized_completed"] == []
    assert prog["completed_credits"] == prog["capstone_required"] == 12


def test_a_module_exactly_at_the_part_time_cap_fills_one_term(monkeypatch):
    # Boundary: credits == the 12-Unit part-time cap must still fit a single term
    # (a `>=` cap test would reject it).  Stubbed because no module with a *sourced*
    # availability carries 12 credits, and the boundary must not ride on an
    # unsourced placement.
    _stub_catalog(monkeypatch, [_module("XX9003", credits=12)])
    plan = build_study_plan(["XX9003"], "part_time")
    assert plan["num_terms"] == 1
    assert plan["semesters"][0]["credits"] == 12
    assert plan["semesters"][0]["at_credit_cap"] is True


# ---------- offering provenance: unknown vs sourced-as-not-offered ----------
def test_only_the_capstone_lacks_sourced_availability():
    """`FT5007` is the one module whose availability no repo source supplies.

    The twelve other codes this test once listed ARE sourced:
    data/_pending/module_catalog.20260531_220239.json is an approved refresh
    (status=resolved, resolved_by=capstone_admin) from
    https://api.nusmods.com/v2/2025-2026/modules carrying a concrete `semesters`
    for every one of them -- and it is where those same rows' name, credits,
    source_url and workload_hours came from.  Dropping only their availability
    let the planner place them in terms the source contradicts (BT5153 into
    Sem 1 when the refresh says Sem 2 only).

    FT5007 is genuinely different: dft_knowledge_base.txt gives it no
    "Availability:" line -- it says only that the capstone spans two semesters --
    and the approved draft does not cover it.  So the omitted key, the repo's
    "unknown", is the honest record here, and `_allowed_in` reads it as flexible.
    """
    catalog = nav_planner._load_catalog()
    assert [c for c, m in catalog.items() if "semesters" not in m] == ["FT5007"]
    assert catalog["FT5007"]["credits"] == 12  # the capstone stays priced


def test_module_sourced_as_not_offered_is_never_scheduled():
    """BMF5358 is sourced "Semester 1 - Not offered | Semester 2 - Not offered".

    data/dft_knowledge_base.txt:395-396.  `semesters: [1]` contradicted that source
    and put the module in Semester 1; `semesters: []` records the source, and a
    module offered in no semester can only be reported as unschedulable.
    """
    assert nav_planner._load_catalog()["BMF5358"]["semesters"] == []
    with pytest.raises(PlanInfeasibleError) as err:
        build_study_plan(["BMF5358"], "full_time")
    assert "BMF5358" in str(err.value) and "not offered" in str(err.value)


def test_a_placement_on_unknown_availability_is_flagged_not_presented_as_sourced():
    # An omitted `semesters` is treated as flexible, so the capstone still lands in a
    # term; the plan must say that placement rests on no sourced availability.
    plan = build_study_plan(["FT5007"], "part_time")
    assert plan["unsourced_offering"] == ["FT5007"]
    # FT5001 is sourced "Semester 1 - Yes | Semester 2 - No" -> nothing to disclaim.
    assert build_study_plan(["FT5001"], "full_time")["unsourced_offering"] == []


def test_the_disclosure_field_reaches_the_agent_response():
    """Every plan a student is shown carries the offering-provenance field.

    This deliberately does NOT assert a non-empty disclosure.  Once the
    availability data was restored from the approved NUSMods refresh, FT5007
    became the only module without sourced availability, and no profile/role
    combination recommends it -- so on real data every disclosure is legitimately
    empty.  Asserting emptiness would be just as wrong: it would break the first
    time a refresh introduces an unsourced module.  What must hold end-to-end is
    that the field survives the agent layer and never names an unplaced module.

    Coverage note: the non-empty path is exercised against real data one layer
    down, by test_a_placement_on_unknown_availability_is_flagged_not_presented_as_sourced.
    """
    p = mock_data.get_profile("1")
    plans = handle(p, {"target_role": "data_analytics"}).data["study_plans"]
    assert plans
    for pathway, plan in plans.items():
        placed = {m["code"] for t in plan["semesters"] for m in t["modules"]}
        assert placed, pathway
        assert "unsourced_offering" in plan, pathway
        assert set(plan["unsourced_offering"]) <= placed, pathway
