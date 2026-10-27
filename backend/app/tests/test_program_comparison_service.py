"""program_comparison workflow through interface.compare(): each mode's
result, the contrasts drawn against MSc DFT, applicant fit, the notes a
degraded or unpersonalised answer carries, and failures."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.domains.specialist.program_comparison import interface, workflow
from app.domains.specialist.program_comparison.errors import ErrorCode, ProgramComparisonStageError
from app.domains.specialist.program_comparison.stages.s4_fit import applicant as fit_stage

TODAY = date(2026, 10, 14)


def _program(pid, *, uni, country, is_target=False, fee=None, currency="SGD", modes=("full_time",),
             curriculum=(), sources=None, deadlines=(), funding=(), **facts):
    return {
        "program_id": pid, "name": f"{pid} name", "short_name": pid, "degree_type": "MSc", "category": "fintech",
        "is_target": is_target, "official_url": f"https://{pid}.edu", "intake_year": 2027,
        "university": {"university_id": uni, "name": uni.upper(), "short_name": uni.upper(), "city": "City",
                       "country_code": country, "country_name": country},
        "facts": {"study_modes": list(modes), **facts},
        "sources": sources or {},
        "fees": [] if fee is None else [{"student_category": "all", "amount": fee, "currency": currency,
                                         "basis": "programme", "source_url": f"https://{pid}.edu/fees"}],
        "deadlines": list(deadlines), "funding": list(funding),
        "curriculum": [{"skill_id": s, "coverage": c, "evidence_courses": [f"{s} course"],
                        "source_url": f"https://{pid}.edu/c"} for s, c in curriculum],
    }


DFT = _program(
    "dft", uni="nus", country="SG", is_target=True, fee=76409, modes=("full_time", "part_time"),
    duration_ft_months=18, ielts_min=6.0, english_waiver="English-medium degree", gmat_gre_policy="recommended",
    curriculum=[("programming", "required"), ("data_analytics", "required"), ("ai_ml", "core_option")],
    sources={"gmat_gre_policy": [
        {"source_url": "https://dft.edu/faq", "quote": "not mandatory", "role": "primary"},
        {"source_url": "https://dft.edu/adm", "quote": "minimum GMAT 650", "role": "conflicting",
         "note": "The FAQ governs."}]},
    deadlines=[{"round_no": 1, "opens_on": date(2026, 10, 1), "closes_on": date(2027, 1, 31),
                "source_url": "https://dft.edu/app"}],
    funding=[{"funding_id": "rebate", "name": "Rebate", "kind": "rebate", "amount_kind": "percent_tuition",
              "percent": 40, "eligible_categories": ["sg_citizen", "sg_pr"], "source_url": "https://nus.edu/r"}],
)
NTU = _program("ntu", uni="ntu", country="SG", fee=68378.75, duration_ft_months=12, ielts_min=6.0,
               curriculum=[("ai_ml", "required"), ("programming", "required")])
UST = _program("ust", uni="hkust", country="HK", fee=405000, currency="HKD", modes=("full_time", "part_time"),
               duration_ft_months=12, ielts_min=6.5, curriculum=[("ai_ml", "required")])
UCL = _program("ucl", uni="ucl", country="GB", modes=())


def run(mode="compare", subjects=("ntu",), **extra):
    return interface.compare({"mode": mode, "today": TODAY, "programs": [DFT, NTU, UST, UCL],
                              "subject_ids": list(subjects), **extra})


def contrasts(result, program_id):
    return {c["kind"]: c["detail"] for c in result["contrasts"] if c["program_id"] == program_id}


def test_compare_lays_dft_against_the_subject():
    r = run()
    assert r["baseline"]["program_id"] == "dft" and [s["program_id"] for s in r["subjects"]] == ["ntu"]
    c = contrasts(r, "ntu")
    assert c["fee_difference"] == {"currency": "SGD", "dft": 76409, "other": 68378.75, "difference": -8030.25}
    assert c["duration_ft_months"]["difference"] == -6
    assert c["study_modes"] == {"dft": ["full_time", "part_time"], "other": ["full_time"]}
    assert c["required_skills"] == {"only_dft": ["data_analytics"], "only_other": ["ai_ml"], "both": ["programming"]}
    assert "country" not in c  # both in Singapore


def test_amounts_in_different_currencies_are_never_converted():
    c = contrasts(run(subjects=("ust",)), "ust")
    assert "fee_difference" not in c
    assert c["different_currency"] == {"dft": {"amount": 76409, "currency": "SGD"},
                                       "other": {"amount": 405000, "currency": "HKD"}}


def test_net_cost_is_compared_when_a_reduction_applies():
    c = contrasts(run(applicant={"residency": "sg_citizen"}), "ntu")
    assert c["net_difference"]["dft"] == 45845.4 and c["net_difference"]["dft_reduced"]
    assert c["net_difference"]["other"] == 68378.75 and not c["net_difference"]["other_reduced"]


def test_target_skills_drive_the_curriculum_contrast():
    r = run(applicant={"target_role": "ML & AI", "target_skills": ["ai_ml", "programming"]})
    assert contrasts(r, "ntu")["target_skills_required"] == {"only_dft": [], "only_other": ["ai_ml"],
                                                            "both": ["programming"]}
    target = r["baseline"]["fit"]["curriculum"]["target"]
    assert target["guaranteed"] == ["programming"] and target["available"] == ["ai_ml"]


def test_english_fit_and_its_contrast():
    r = run(subjects=("ust",), applicant={"english_medium_degree": False,
                                          "tests": [{"key": "IELTS", "score": 6.0, "test_date": "2026-01-10"}]})
    assert r["baseline"]["fit"]["admission"]["english"]["status"] == "met"
    assert contrasts(r, "ust")["english_fit"] == {"dft": "met", "other": "not_met"}


def test_conflicts_and_sources_come_with_the_programme():
    base = run(dimensions=["admission"])["baseline"]
    assert base["conflicts"][0]["field"] == "gmat_gre_policy" and base["conflicts"][0]["note"] == "The FAQ governs."
    assert "https://dft.edu/faq" in base["sources"] and "https://dft.edu/adm" not in base["sources"]


def test_asked_aspects_limit_the_answer():
    r = run(dimensions=["duration"])
    assert r["dimensions"] == ["duration"]
    assert set(r["baseline"]["facts"]) == {"duration"}
    assert {c["dimension"] for c in r["contrasts"]} == {"duration"}


def test_detail_answers_about_one_programme():
    r = run("detail", ("dft",), dimensions=["deadlines"], applicant={"residency": "sg_pr"})
    assert r["baseline"]["program_id"] == "dft" and r["subjects"] == [] and r["contrasts"] == []
    assert r["baseline"]["fit"]["deadlines"]["next_round"]["days_left"] == 109


def test_explore_filters_without_ranking():
    r = run("explore", (), conditions={"study_mode": "part_time"})
    assert [m["program_id"] for m in r["matches"]] == ["ust"]  # UCL's modes aren't on file: left out
    assert r["baseline"]["program_id"] == "dft"
    none = run("explore", (), conditions={"countries": ["AU"]})
    assert none["matches"] == [] and ErrorCode.NO_MATCHING_PROGRAMMES in [d["code"] for d in none["diagnostics"]]


def test_an_unknown_applicant_gets_facts_and_says_so():
    r = run()
    assert not r["personalised"]
    assert ErrorCode.NOT_PERSONALISED in [d["code"] for d in r["diagnostics"]]


def test_an_intake_mismatch_is_noted():
    r = run(applicant={"intake_year": 2028})
    assert ErrorCode.INTAKE_MISMATCH in [d["code"] for d in r["diagnostics"]]
    assert "AY2028/29" in r["notes"][0]


def test_unsupported_decision_factor_is_noted():
    r = run(applicant={"decision_factors": ["brand_ranking"]})
    assert r["unsupported_factors"] == ["brand_ranking"] and any("Rankings" in n for n in r["notes"])


def test_applicant_fit_failure_degrades_to_facts(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("fit broke")
    monkeypatch.setattr(fit_stage, "fit", boom)
    r = run(applicant={"residency": "sg_citizen"})
    assert r["workflow_status"] == "degraded" and r["baseline"]["fit"] == {}
    assert r["baseline"]["facts"]["cost"]


def test_assembly_failure_raises_a_stage_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("assembly broke")
    monkeypatch.setattr(workflow.MODES["compare"], "assemble", boom)
    with pytest.raises(ProgramComparisonStageError) as err:
        run()
    assert err.value.code == ErrorCode.RESULT_ASSEMBLY_FAILED


def test_invalid_report_is_a_validation_error():
    with pytest.raises(ProgramComparisonStageError) as err:
        run(subjects=("dft",))
    assert err.value.code == ErrorCode.INPUT_INVALID and err.value.status_code == 422


def test_the_response_is_plain_json():
    r = run(applicant={"residency": "sg_citizen", "tests": [{"key": "GRE", "score": 320, "test_date": "2025-01-01"}]})
    json.dumps(r)
    assert r["today"] == "2026-10-14"


def test_contrast_never_names_a_winner():
    assert not any(word in json.dumps(run(subjects=("ntu", "ust"))["contrasts"]).lower()
                   for word in ("better", "best", "worse", "rank"))


# --- "which suits me?" (stages/s5_goals) ---

def test_asking_which_suits_checks_each_programme_against_the_goals():
    applicant = {"residency": "international", "decision_factors": ["duration", "cost"],
                 "tests": [{"key": "IELTS", "score": 6.0, "test_date": "2026-03-01"}],
                 "target_role": "Data Analytics", "target_skills": ["programming", "data_analytics"]}
    r = run(subjects=("ntu", "ust"), applicant=applicant, asks_which_suits=True)
    goals = {g["goal"]: g for g in r["goal_check"]["goals"]}
    # DFT requires both target skills, NTU one, HKUST none.
    assert goals["target_role"]["ahead"] == ["dft"]
    # IELTS 6.0 meets DFT's and NTU's 6.0, not HKUST's 6.5.
    assert goals["english"]["ahead"] == ["dft", "ntu"]
    assert goals["duration"]["ahead"] == ["ntu", "ust"]
    # SGD and HKD fees are never converted to compare them.
    assert goals["cost"]["ahead"] == [] and goals["cost"]["not_comparable"] == "different currencies"
    # Shared leads count: DFT 2 (target role, English), NTU 2 (English, duration), HKUST 1.
    assert r["goal_check"]["ahead_count"] == {"dft": 2, "ntu": 2, "ust": 1}
    assert r["goal_check"]["lead"] is None  # the goals split


def test_a_split_names_no_lead_and_the_check_needs_the_question():
    applicant = {"decision_factors": ["duration"], "target_role": "AI", "target_skills": ["ai_ml"]}
    r = run(subjects=("ntu",), applicant=applicant, asks_which_suits=True)
    assert r["goal_check"]["ahead_count"] == {"dft": 0, "ntu": 2}  # ai_ml required at NTU; shorter
    assert r["goal_check"]["lead"] == "ntu"
    level = run(subjects=("ust",), applicant={"decision_factors": ["flexibility"]}, asks_which_suits=True)
    # Both offer part-time: the goal is level, so no programme is named.
    assert level["goal_check"]["goals"][0]["ahead"] == [] and level["goal_check"]["lead"] is None
    assert run(subjects=("ntu",), applicant=applicant)["goal_check"] is None  # not asked
