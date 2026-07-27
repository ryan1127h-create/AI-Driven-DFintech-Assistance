"""Deterministic tests for #7 Navigator v2 study-path planner (no LLM)."""
from agents.navigator.agent import handle
from agents.navigator.planner import (
    base_code,
    build_study_plan,
    graduation_progress,
    prereq_satisfied,
    prereq_warnings,
    what_if_pathways,
)
from common import mock_data
from common.profile import TargetRole


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
    codes = ["BMS5312", "BMD5301", "BMF5358", "BT5153", "DBA5107"]
    plan = build_study_plan(codes, "full_time")
    assert all(t["credits"] <= 20 for t in plan["semesters"])


def test_part_time_smaller_cap_more_terms():
    codes = ["BMS5312", "BMD5301", "BMF5358", "BT5153"]
    ft = build_study_plan(codes, "full_time")
    pt = build_study_plan(codes, "part_time")
    assert all(t["credits"] <= 12 for t in pt["semesters"])
    assert pt["num_terms"] >= ft["num_terms"]


def test_study_plan_respects_offered_semester():
    # BT5153 is offered only in Sem 2 -> must land in a Sem 2 term.
    plan = build_study_plan(["BT5153"], "full_time")
    bt = next(t for t in plan["semesters"] for m in t["modules"] if m["code"] == "BT5153")
    assert bt["semester"] == 2


def test_what_if_returns_both_pathways():
    wf = what_if_pathways(["BMS5312", "BT5153"])
    assert set(wf) == {"full_time", "part_time"}


# ---------- agent integration ----------
def test_handle_includes_planning_fields():
    p = mock_data.get_profile("1")  # completed_modules=["BMD5301"]
    resp = handle(p, {"target_role": "data_analytics"})
    d = resp.data
    assert "graduation_progress" in d and d["graduation_progress"]["completed_credits"] == 4
    assert "study_plans" in d and set(d["study_plans"]) == {"full_time", "part_time"}
    # BMF5360 prereq unmet -> warning surfaced
    assert any(w["code"] == "BMF5360" for w in d["prereq_warnings"])


# ---------- B: progress never double-counts completed ----------
def test_graduation_progress_excludes_completed_from_planned():
    completed = ["BMS5312"]
    prog = graduation_progress(completed, ["BMS5312", "FT5001"])
    only_remaining = graduation_progress(completed, ["FT5001"])
    assert prog["planned_credits"] == only_remaining["planned_credits"]
