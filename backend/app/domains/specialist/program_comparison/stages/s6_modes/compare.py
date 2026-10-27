"""
compare — MSc DFT as the baseline against one to three programmes, aspect
by aspect, plus the differences that can be stated from the facts alone.

A contrast is only drawn where both sides have the fact. Amounts in
different currencies are set side by side, never converted. A contrast
names a difference; it never says which side is better — that depends
on the applicant, and the reply relates it to their own situation.
"""

from __future__ import annotations

from app.domains.specialist.program_comparison.models import ApplicantFit, Conditions, Contrast, ProgramView
from app.domains.specialist.program_comparison.stages.s6_modes.base import program_result


def _single_fee(view: ProgramView) -> dict | None:
    fees = [f for f in view.fees if f["basis"] == "programme"]
    return fees[0] if len(fees) == 1 else None


def _cost(dft: ProgramView, other: ProgramView, fits: dict[str, ApplicantFit]) -> list[Contrast]:
    a, b = _single_fee(dft), _single_fee(other)
    if not (a and b):
        return []
    if a["currency"] != b["currency"]:
        return [Contrast("cost", other.program_id, "different_currency", {
            "dft": {"amount": a["amount"], "currency": a["currency"]},
            "other": {"amount": b["amount"], "currency": b["currency"]}})]
    found = [Contrast("cost", other.program_id, "fee_difference", {
        "currency": a["currency"], "dft": a["amount"], "other": b["amount"],
        "difference": round(b["amount"] - a["amount"], 2)})]
    net_a = fits[dft.program_id].by_dimension.get("cost", {}).get("net_amount") if dft.program_id in fits else None
    net_b = fits[other.program_id].by_dimension.get("cost", {}).get("net_amount") if other.program_id in fits else None
    if net_a is not None or net_b is not None:
        da, db = net_a if net_a is not None else a["amount"], net_b if net_b is not None else b["amount"]
        found.append(Contrast("cost", other.program_id, "net_difference", {
            "currency": a["currency"], "dft": da, "other": db, "difference": round(db - da, 2),
            "dft_reduced": net_a is not None, "other_reduced": net_b is not None}))
    return found


def _duration(dft: ProgramView, other: ProgramView) -> list[Contrast]:
    found = []
    for key in ("duration_ft_months", "duration_pt_months"):
        a, b = dft.raw_facts.get(key), other.raw_facts.get(key)
        if a is not None and b is not None and a != b:
            found.append(Contrast("duration", other.program_id, key, {"dft": a, "other": b, "difference": b - a}))
    return found


def _flexibility(dft: ProgramView, other: ProgramView) -> list[Contrast]:
    found = []
    for key in ("study_modes", "intake_months"):
        a, b = dft.raw_facts.get(key), other.raw_facts.get(key)
        if a and b and set(a) != set(b):
            found.append(Contrast("flexibility", other.program_id, key, {"dft": list(a), "other": list(b)}))
    return found


def _admission(dft: ProgramView, other: ProgramView, fits: dict[str, ApplicantFit]) -> list[Contrast]:
    found = []
    for key in ("gmat_gre_policy", "ielts_min", "toefl_ibt_band_min", "work_exp_policy"):
        a, b = dft.raw_facts.get(key), other.raw_facts.get(key)
        if a is not None and b is not None and a != b:
            found.append(Contrast("admission", other.program_id, key, {"dft": a, "other": b}))
    fa = fits.get(dft.program_id)
    fb = fits.get(other.program_id)
    if fa and fb:
        ea = fa.by_dimension.get("admission", {}).get("english", {}).get("status")
        eb = fb.by_dimension.get("admission", {}).get("english", {}).get("status")
        if ea and eb and ea != eb:
            found.append(Contrast("admission", other.program_id, "english_fit", {"dft": ea, "other": eb}))
    return found


def _skills(view: ProgramView, level: str) -> set[str]:
    return {a["skill_id"] for a in view.curriculum if a["coverage"] == level}


def _curriculum(dft: ProgramView, other: ProgramView, fits: dict[str, ApplicantFit]) -> list[Contrast]:
    fa, fb = fits.get(dft.program_id), fits.get(other.program_id)
    ta = fa.by_dimension.get("curriculum", {}).get("target") if fa else None
    tb = fb.by_dimension.get("curriculum", {}).get("target") if fb else None
    if ta and tb:
        a, b = set(ta["guaranteed"]), set(tb["guaranteed"])
        kind = "target_skills_required"
    else:
        a, b = _skills(dft, "required"), _skills(other, "required")
        kind = "required_skills"
    if a == b:
        return []
    return [Contrast("curriculum", other.program_id, kind, {
        "only_dft": sorted(a - b), "only_other": sorted(b - a), "both": sorted(a & b)})]


def _deadlines(dft: ProgramView, other: ProgramView, fits: dict[str, ApplicantFit]) -> list[Contrast]:
    def next_close(view):
        fit = fits.get(view.program_id)
        nxt = fit.by_dimension.get("deadlines", {}).get("next_round") if fit else None
        return nxt["closes_on"] if nxt else None
    a, b = next_close(dft), next_close(other)
    if a is None and b is None:
        return []
    return [Contrast("deadlines", other.program_id, "next_close", {"dft": a, "other": b})]


def _location(dft: ProgramView, other: ProgramView) -> list[Contrast]:
    if dft.country_code == other.country_code:
        return []
    return [Contrast("location", other.program_id, "country", {
        "dft": f"{dft.city}, {dft.country}", "other": f"{other.city}, {other.country}"})]


class Compare:
    def assemble(self, views, fits, *, target_id, subject_ids, dimensions, conditions: Conditions):
        dft = views[target_id]
        contrasts: list[Contrast] = []
        for sid in subject_ids:
            other = views[sid]
            by_dimension = {
                "cost": lambda: _cost(dft, other, fits),
                "duration": lambda: _duration(dft, other),
                "flexibility": lambda: _flexibility(dft, other),
                "admission": lambda: _admission(dft, other, fits),
                "curriculum": lambda: _curriculum(dft, other, fits),
                "deadlines": lambda: _deadlines(dft, other, fits),
                "location": lambda: _location(dft, other),
            }
            for d in dimensions:
                if d in by_dimension:
                    contrasts.extend(by_dimension[d]())
        baseline = program_result(dft, fits.get(target_id), dimensions)
        subjects = tuple(program_result(views[s], fits.get(s), dimensions) for s in subject_ids)
        return baseline, subjects, (), tuple(contrasts)
