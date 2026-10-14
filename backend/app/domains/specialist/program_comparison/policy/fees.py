"""
Which tuition fee applies to an applicant, and what they would pay after
the reductions that come without applying.

Fee category: a programme's 'domestic' rate is for its own country's
students. The profile records only Singapore status (citizen, PR or
international), so an applicant is known to be domestic or international
only for a Singapore programme; elsewhere both rates are shown.

Net cost is estimated only from reductions the applicant certainly gets
without applying: rebates and grants whose eligibility the profile
settles, with a stated amount. Programmes rarely let several stack, and
the catalogue doesn't record which do, so only the largest is deducted
and the rest are listed as possibly applying too — the estimate may be
high, never low. Scholarships, loans and subsidies are never deducted:
they are applied for and not certain.
"""

from __future__ import annotations

from dataclasses import dataclass

AUTOMATIC_KINDS = frozenset({"rebate", "grant"})


@dataclass(frozen=True)
class Reduction:
    funding_id: str
    name: str
    kind: str
    amount_kind: str
    percent: float | None
    amount: float | None
    currency: str | None
    # True: the profile shows the applicant qualifies; None: it can't tell.
    eligible: bool | None
    automatic: bool


@dataclass(frozen=True)
class CostEstimate:
    # The fee rows that apply: one when the category is settled (or the
    # programme has a single rate), else every rate.
    fees: tuple[dict, ...]
    applicant_category: str | None
    deduction: Reduction | None
    deduction_amount: float | None
    net_amount: float | None
    # Other reductions the applicant does or may qualify for.
    other_reductions: tuple[Reduction, ...]


def applicant_category(residency: str | None, program_country: str) -> str | None:
    if residency is None or program_country != "SG":
        return None
    return "domestic" if residency in ("sg_citizen", "sg_pr") else "international"


def applicable_fees(fees: list[dict], category: str | None) -> tuple[dict, ...]:
    shared = [f for f in fees if f["student_category"] == "all"]
    if shared:
        return tuple(shared)
    if category:
        matching = [f for f in fees if f["student_category"] == category]
        if matching:
            return tuple(matching)
    return tuple(fees)


def eligibility(categories: list[str] | None, *, residency: str | None, category: str | None,
                is_nus_alumnus: bool | None, university_id: str) -> bool | None:
    """True / False when the profile settles it, None when it can't. Only
    NUS alumni status is on file, so another university's alumni award is
    unknown."""
    if categories is None:
        return None
    results = []
    for c in categories:
        if c == "all":
            results.append(True)
        elif c in ("sg_citizen", "sg_pr"):
            results.append(None if residency is None else residency == c)
        elif c in ("domestic", "international"):
            results.append(None if category is None else category == c)
        elif c == "alumni":
            results.append(is_nus_alumnus if university_id == "nus" else None)
    if True in results:
        return True
    return None if None in results else False


def _value(reduction: Reduction, fee: dict) -> float | None:
    if reduction.amount_kind == "percent_tuition" and reduction.percent:
        return round(fee["amount"] * reduction.percent / 100, 2)
    if reduction.amount_kind == "fixed" and reduction.amount is not None and reduction.currency == fee["currency"]:
        return min(reduction.amount, fee["amount"])
    return None


def estimate(fees: list[dict], funding: list[dict], *, residency: str | None, is_nus_alumnus: bool | None,
             university_id: str, program_country: str) -> CostEstimate:
    category = applicant_category(residency, program_country)
    shown = applicable_fees(fees, category)
    reductions = []
    for f in funding:
        eligible = eligibility(f.get("eligible_categories"), residency=residency, category=category,
                               is_nus_alumnus=is_nus_alumnus, university_id=university_id)
        if eligible is False:
            continue
        automatic = (eligible is True and f["kind"] in AUTOMATIC_KINDS
                     and f["amount_kind"] in ("percent_tuition", "fixed"))
        reductions.append(Reduction(
            f["funding_id"], f["name"], f["kind"], f["amount_kind"], f.get("percent"), f.get("amount"),
            f.get("currency"), eligible, automatic,
        ))

    deduction = amount = net = None
    if len(shown) == 1 and shown[0]["basis"] == "programme":
        fee = shown[0]
        valued = [(r, _value(r, fee)) for r in reductions if r.automatic]
        valued = [(r, v) for r, v in valued if v]
        if valued:
            deduction, amount = max(valued, key=lambda pair: pair[1])
            net = round(fee["amount"] - amount, 2)
    others = tuple(r for r in reductions if r is not deduction)
    return CostEstimate(shown, category, deduction, amount, net, others)
