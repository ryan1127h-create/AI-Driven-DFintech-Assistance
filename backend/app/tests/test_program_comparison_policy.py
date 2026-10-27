"""program_comparison/policy: fee category and net cost, deadline status,
test-score and work checks, curriculum coverage and the order of
aspects. Figures follow the real catalogue (MSc DFT AY2027/28)."""

from __future__ import annotations

from datetime import date

import pytest

from app.domains.specialist.program_comparison.policy import curriculum, deadlines, dimensions, fees, requirements

TODAY = date(2026, 10, 14)
DFT_FEE = [{"student_category": "all", "amount": 76409, "currency": "SGD", "basis": "programme"}]
NUS_REBATES = [
    {"funding_id": "sg", "name": "Rebate", "kind": "rebate", "amount_kind": "percent_tuition", "percent": 40,
     "eligible_categories": ["sg_citizen", "sg_pr"]},
    {"funding_id": "alumni", "name": "Alumni rebate", "kind": "rebate", "amount_kind": "percent_tuition", "percent": 20,
     "eligible_categories": ["alumni"]},
    {"funding_id": "grtii", "name": "GRTII", "kind": "scholarship", "amount_kind": "fixed", "amount": 45000,
     "currency": "SGD", "eligible_categories": None},
]


def _estimate(residency=None, alumnus=None, fee=DFT_FEE, funding=NUS_REBATES, uni="nus", country="SG"):
    return fees.estimate(fee, funding, residency=residency, is_nus_alumnus=alumnus,
                         university_id=uni, program_country=country)


# ── fees ──────────────────────────────────────────────────────────────────

def test_citizen_gets_the_rebate_deducted():
    e = _estimate("sg_citizen")
    assert e.deduction.funding_id == "sg"
    assert (e.deduction_amount, e.net_amount) == (30563.6, 45845.4)
    # The scholarship is applied for, so it is only listed.
    assert [r.funding_id for r in e.other_reductions] == ["alumni", "grtii"]
    assert not next(r for r in e.other_reductions if r.funding_id == "grtii").automatic


def test_only_the_largest_reduction_is_deducted():
    e = _estimate("sg_pr", alumnus=True)
    assert e.deduction.funding_id == "sg"
    assert [r.funding_id for r in e.other_reductions] == ["alumni", "grtii"]


def test_international_alumnus_gets_the_alumni_rebate():
    e = _estimate("international", alumnus=True)
    assert e.deduction.funding_id == "alumni" and e.net_amount == 61127.2
    assert [r.funding_id for r in e.other_reductions] == ["grtii"]  # the SG rebate doesn't apply


def test_nothing_is_deducted_without_a_profile():
    e = _estimate()
    assert e.deduction is None and e.net_amount is None
    assert {r.funding_id: r.eligible for r in e.other_reductions} == {"sg": None, "alumni": None, "grtii": None}


def test_domestic_and_international_rates_outside_singapore_both_show():
    hku = [{"student_category": "domestic", "amount": 275000, "currency": "HKD", "basis": "programme"},
           {"student_category": "international", "amount": 375000, "currency": "HKD", "basis": "programme"}]
    e = _estimate("international", fee=hku, funding=[], uni="hku", country="HK")
    assert e.applicant_category is None and len(e.fees) == 2 and e.net_amount is None


def test_singapore_category_picks_one_rate():
    rates = [{"student_category": "domestic", "amount": 1, "currency": "SGD", "basis": "programme"},
             {"student_category": "international", "amount": 2, "currency": "SGD", "basis": "programme"}]
    assert [f["amount"] for f in _estimate("sg_pr", fee=rates, funding=[]).fees] == [1]


def test_other_universities_alumni_awards_stay_unknown():
    smu = [{"funding_id": "smu", "name": "SMU alumni", "kind": "rebate", "amount_kind": "fixed", "amount": 8000,
            "currency": "SGD", "eligible_categories": ["alumni"]}]
    e = _estimate("international", alumnus=True, funding=smu, uni="smu")
    assert e.deduction is None and e.other_reductions[0].eligible is None


def test_a_fixed_grant_in_another_currency_is_not_deducted():
    grant = [{"funding_id": "g", "name": "G", "kind": "grant", "amount_kind": "fixed", "amount": 10,
              "currency": "HKD", "eligible_categories": ["all"]}]
    assert _estimate(funding=grant).net_amount is None


# ── deadlines ─────────────────────────────────────────────────────────────

def test_rounds_are_open_closed_or_upcoming():
    status = deadlines.status([
        {"round_no": 1, "round_label": "R1", "opens_on": date(2026, 8, 20), "closes_on": date(2026, 9, 29)},
        {"round_no": 2, "round_label": "R2", "opens_on": date(2026, 9, 30), "closes_on": date(2027, 1, 6)},
        {"round_no": 3, "round_label": "R3", "opens_on": date(2027, 1, 7), "closes_on": date(2027, 3, 10)},
    ], TODAY)
    assert [r.status for r in status.rounds] == ["closed", "open", "upcoming"]
    assert status.next_round.round_no == 2 and status.next_round.days_left == 84
    assert not status.all_closed


def test_a_round_without_an_opening_date_is_open_until_it_closes():
    status = deadlines.status([{"round_no": 1, "opens_on": None, "closes_on": date(2026, 12, 1)}], TODAY)
    assert status.rounds[0].status == "open"


def test_all_rounds_closed():
    status = deadlines.status([{"round_no": 1, "opens_on": None, "closes_on": date(2026, 7, 15)}], TODAY)
    assert status.all_closed and status.next_round is None


# ── requirements ──────────────────────────────────────────────────────────

def _english(tests, medium=None, waiver=True, **minimums):
    m = {"toefl_ibt_min": 90, "toefl_band_min": 4.5, "ielts_min": 6.0, "ielts_sub_min": None, **minimums}
    return requirements.english(tests, english_medium_degree=medium, has_waiver=waiver, today=TODAY, **m)


def test_english_medium_degree_waives_when_the_programme_says_so():
    assert _english([], medium=True).status == "waived"
    assert _english([], medium=True, waiver=False).status == "missing"


def test_ielts_against_the_minimum():
    assert _english([{"key": "IELTS", "score": 6.5, "test_date": date(2025, 3, 1)}]).status == "met"
    assert _english([{"key": "IELTS", "score": 6.5, "test_date": date(2025, 3, 1)}], ielts_min=7.0).status == "not_met"


def test_toefl_new_scale_is_checked_against_the_new_minimum():
    check = _english([{"key": "TOEFL", "score": 4.5, "test_date": date(2026, 3, 1)}])
    assert (check.status, check.minimum) == ("met", 4.5)
    assert _english([{"key": "TOEFL", "score": 85, "test_date": date(2025, 3, 1)}]).status == "not_met"


def test_expired_language_test_doesnt_count():
    assert _english([{"key": "IELTS", "score": 8, "test_date": date(2024, 10, 1)}]).status == "missing"


def test_ielts_sub_scores_are_reported_unchecked():
    assert _english([{"key": "IELTS", "score": 7, "test_date": None}], ielts_sub_min=6.5).sub_scores_unchecked


def test_no_published_minimum():
    assert _english([], toefl_ibt_min=None, toefl_band_min=None, ielts_min=None).status == "no_data"


@pytest.mark.parametrize("tests, policy, expected", [
    ([{"key": "GRE", "score": 323, "test_date": date(2024, 10, 8)}], "required", "have_score"),
    ([{"key": "GMAT", "score": 700, "test_date": date(2020, 1, 1)}], "required", "required"),  # expired
    ([], "recommended", "recommended"),
    ([], "optional", "not_needed"),
    ([], "required_waivable", "required_waivable"),
    ([], None, "no_data"),
])
def test_gmat_gre(tests, policy, expected):
    assert requirements.gmat_gre(tests, policy, TODAY).status == expected


@pytest.mark.parametrize("band, policy, minimum, expected", [
    ("1-3", "preferred", 2, "short"),   # counted at 1 year
    ("3-5", "preferred", 2, "met"),
    (None, "preferred", 2, "unknown"),
    ("3-5", "not_required", None, "not_required"),
    ("3-5", "preferred", None, "preferred"),
    ("3-5", None, None, "no_data"),
])
def test_work_experience(band, policy, minimum, expected):
    assert requirements.work_experience(band, policy, minimum).status == expected


# ── curriculum and dimensions ─────────────────────────────────────────────

HKUST_CURRICULUM = [
    {"skill_id": "finance", "coverage": "required", "evidence_courses": ["FINA 5120 Corporate Finance"]},
    {"skill_id": "ai_ml", "coverage": "required", "evidence_courses": ["MFIT 5001 AI for FinTech"]},
    {"skill_id": "security", "coverage": "none", "evidence_courses": []},
]


def test_target_skills_split_by_certainty():
    m = curriculum.match(HKUST_CURRICULUM, ["ai_ml", "programming", "security"])
    assert (m.guaranteed, m.available, m.not_taught, m.unknown) == (("ai_ml",), (), ("security",), ("programming",))
    assert m.skills[0].courses == ("MFIT 5001 AI for FinTech",)


def test_depth_reads_tech_and_finance_sides():
    d = curriculum.depth(HKUST_CURRICULUM)
    assert d["tech"].guaranteed == ("ai_ml",) and d["finance"].guaranteed == ("finance",)


def test_asked_dimensions_are_the_whole_answer():
    assert dimensions.order(["deadlines", "cost"], ["tech_depth"]) == ("cost", "deadlines")


def test_decision_factors_lead_otherwise():
    order = dimensions.order([], ["scholarship", "tech_depth", "brand_ranking"])
    assert order[:2] == ("funding", "curriculum") and len(order) == len(dimensions.DEFAULT_ORDER)
