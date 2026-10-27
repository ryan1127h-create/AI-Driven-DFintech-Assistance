"""
S4 — reads one programme against what is known about the applicant, aspect
by aspect, with the rule's inputs kept so the reply can say why. An aspect
nothing known about the applicant bears on is left out rather than
guessed; nothing is ever scored or ranked.

  cost        which rate applies, the net after the one certain automatic
              reduction, the other reductions that do or may apply
  admission   English, GMAT/GRE and work experience against the minimums
  curriculum  the target role's skills, and technology/finance depth
  deadlines   the next round open to the applicant's fee category
  flexibility whether the applicant's start fits an intake; part-time
              availability for someone with work experience
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.domains.specialist.program_comparison.models import Applicant, ApplicantFit, ProgramView
from app.domains.specialist.program_comparison.policy import curriculum, deadlines, fees, requirements


def _reduction(r: fees.Reduction) -> dict:
    return {k: v for k, v in asdict(r).items() if v is not None}


def _cost(view: ProgramView, a: Applicant) -> dict:
    est = fees.estimate(list(view.fees), list(view.funding), residency=a.residency,
                        is_nus_alumnus=a.is_nus_alumnus, university_id=view.university_id,
                        program_country=view.country_code)
    result = {
        "applicant_category": est.applicant_category,
        "fees": [{k: f[k] for k in ("student_category", "amount", "currency", "basis") if k in f} for f in est.fees],
        "other_reductions": [_reduction(r) for r in est.other_reductions],
    }
    if est.deduction:
        result.update(deduction=_reduction(est.deduction), deduction_amount=est.deduction_amount,
                      net_amount=est.net_amount, currency=est.fees[0]["currency"])
    return result


def _admission(view: ProgramView, a: Applicant, today: date) -> dict:
    f = view.raw_facts
    tests = list(a.tests)
    result = {}
    if tests or a.english_medium_degree is not None:
        result["english"] = asdict(requirements.english(
            tests, english_medium_degree=a.english_medium_degree, toefl_ibt_min=f.get("toefl_ibt_min"),
            toefl_band_min=f.get("toefl_ibt_band_min"), ielts_min=f.get("ielts_min"),
            ielts_sub_min=f.get("ielts_sub_min"), has_waiver=bool(f.get("english_waiver")), today=today))
    if tests or f.get("gmat_gre_policy"):
        result["gmat_gre"] = asdict(requirements.gmat_gre(tests, f.get("gmat_gre_policy"), today))
    if a.work_band:
        result["work"] = asdict(requirements.work_experience(
            a.work_band, f.get("work_exp_policy"), f.get("work_exp_min_years")))
    return result


def _curriculum(view: ProgramView, a: Applicant) -> dict:
    areas = list(view.curriculum)
    result = {}
    if a.target_skills:
        m = curriculum.match(areas, a.target_skills)
        result["target"] = {"role": a.target_role, "guaranteed": list(m.guaranteed), "available": list(m.available),
                            "not_taught": list(m.not_taught), "unknown": list(m.unknown)}
    wants = {"tech_depth": "tech", "finance_depth": "finance"}
    for factor, side in wants.items():
        if factor in a.decision_factors:
            m = curriculum.depth(areas)[side]
            result[f"{side}_depth"] = {"guaranteed": list(m.guaranteed), "available": list(m.available),
                                       "unknown": list(m.unknown)}
    return result


def _deadlines(view: ProgramView, a: Applicant, today: date) -> dict:
    category = fees.applicant_category(a.residency, view.country_code)
    rounds = [r for r in view.deadlines if r.get("applicant_category", "all") in ("all", category)]
    if not rounds:
        return {}
    st = deadlines.status(rounds, today)
    result = {"all_closed": st.all_closed}
    if st.next_round:
        result["next_round"] = {k: v for k, v in asdict(st.next_round).items() if v is not None}
    return result


def _flexibility(view: ProgramView, a: Applicant) -> dict:
    f = view.raw_facts
    result = {}
    if a.work_band and requirements.WORK_YEARS_LOWER_BOUND.get(a.work_band, 0) >= 1 and f.get("study_modes"):
        result["part_time_available"] = "part_time" in f["study_modes"]
    return result


def fit(view: ProgramView, applicant: Applicant, today: date) -> ApplicantFit:
    by_dimension = {
        "cost": _cost(view, applicant),
        "admission": _admission(view, applicant, today),
        "curriculum": _curriculum(view, applicant),
        "deadlines": _deadlines(view, applicant, today),
        "flexibility": _flexibility(view, applicant),
    }
    mismatch = applicant.intake_year is not None and applicant.intake_year != view.intake_year
    return ApplicantFit(view.program_id, {d: v for d, v in by_dimension.items() if v}, mismatch)
