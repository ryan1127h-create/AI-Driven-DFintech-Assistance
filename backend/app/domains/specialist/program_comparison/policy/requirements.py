"""
An applicant's test scores and work experience against one programme's
admission requirements.

English: a waiver is only assumed when the applicant's degree was taught
in English and the programme publishes such a waiver. TOEFL changed scale
on 21 January 2026 (0-120 to 1-6); a score of 6 or below is read on the
new scale and checked against the programme's new-scale minimum. IELTS
sub-scores are not on file, so a sub-score minimum is reported as
unchecked rather than met. Test validity: language tests 2 years,
GMAT/GRE 5 years (the profile field's own rule); a test without a date
is taken as valid.

Work experience is stored as a band and counted at its lower bound, never
overstating it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

LANGUAGE_VALID_YEARS = 2
GMAT_GRE_VALID_YEARS = 5
TOEFL_NEW_SCALE_MAX = 6
WORK_YEARS_LOWER_BOUND = {"0": 0, "<1": 0, "1-3": 1, "3-5": 3, "5-10": 5, "10+": 10}


@dataclass(frozen=True)
class EnglishCheck:
    # "met" | "not_met" | "waived" | "missing" (no usable test on file) |
    # "no_data" (the programme publishes no minimum)
    status: str
    test: str | None = None
    score: float | None = None
    minimum: float | None = None
    sub_scores_unchecked: bool = False


@dataclass(frozen=True)
class GmatCheck:
    # "have_score" | "not_needed" | "recommended" | "required" |
    # "required_waivable" | "no_data"
    status: str
    policy: str | None
    test: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class WorkCheck:
    # "met" | "short" | "not_required" | "preferred" | "unknown" | "no_data"
    status: str
    applicant_years: int | None
    minimum_years: float | None


def _valid(test: dict, years: int, today: date) -> bool:
    taken = test.get("test_date")
    if taken is None:
        return True
    try:
        expiry = taken.replace(year=taken.year + years)
    except ValueError:  # 29 February
        expiry = taken.replace(year=taken.year + years, day=28)
    return today <= expiry


def english(tests: list[dict], *, english_medium_degree: bool | None, toefl_ibt_min: float | None,
            toefl_band_min: float | None, ielts_min: float | None, ielts_sub_min: float | None,
            has_waiver: bool, today: date) -> EnglishCheck:
    if english_medium_degree and has_waiver:
        return EnglishCheck("waived")
    if toefl_ibt_min is None and toefl_band_min is None and ielts_min is None:
        return EnglishCheck("no_data")

    checked: list[EnglishCheck] = []
    for t in tests:
        if t.get("score") is None or not _valid(t, LANGUAGE_VALID_YEARS, today):
            continue
        score = t["score"]
        if t["key"] == "TOEFL":
            minimum = toefl_band_min if score <= TOEFL_NEW_SCALE_MAX else toefl_ibt_min
        elif t["key"] == "IELTS":
            minimum = ielts_min
        else:
            continue
        if minimum is None:
            continue
        sub = t["key"] == "IELTS" and ielts_sub_min is not None
        checked.append(EnglishCheck("met" if score >= minimum else "not_met", t["key"], score, minimum, sub))
    met = [c for c in checked if c.status == "met"]
    if met:
        return met[0]
    if checked:
        return checked[0]
    return EnglishCheck("missing")


def gmat_gre(tests: list[dict], policy: str | None, today: date) -> GmatCheck:
    valid = [t for t in tests if t["key"] in ("GMAT", "GRE") and _valid(t, GMAT_GRE_VALID_YEARS, today)]
    if valid:
        return GmatCheck("have_score", policy, valid[0]["key"], valid[0].get("score"))
    if policy is None:
        return GmatCheck("no_data", None)
    if policy in ("optional", "not_considered"):
        return GmatCheck("not_needed", policy)
    return GmatCheck(policy, policy)


def work_experience(band: str | None, policy: str | None, minimum: float | None) -> WorkCheck:
    years = WORK_YEARS_LOWER_BOUND.get(band) if band else None
    if policy is None:
        return WorkCheck("no_data", years, minimum)
    if policy == "not_required":
        return WorkCheck("not_required", years, minimum)
    if years is None:
        return WorkCheck("unknown", years, minimum)
    if minimum is None:
        return WorkCheck("preferred" if policy == "preferred" else "unknown", years, minimum)
    return WorkCheck("met" if years >= minimum else "short", years, minimum)
