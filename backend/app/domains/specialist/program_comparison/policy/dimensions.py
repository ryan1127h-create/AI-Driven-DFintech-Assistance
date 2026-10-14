"""
Which aspects a comparison covers, and in what order.

Aspects the message asks about are the whole answer. Otherwise the
applicant's decision factors (profile decision_factors) come first, then
the rest in the default order — cost and curriculum lead because they are
what applicants most often weigh MSc DFT on.
"""

from __future__ import annotations

DEFAULT_ORDER = ("cost", "curriculum", "duration", "admission", "flexibility", "funding", "deadlines", "location")

FACTOR_DIMENSIONS = {
    "cost": ("cost",),
    "duration": ("duration",),
    "tech_depth": ("curriculum",),
    "finance_depth": ("curriculum",),
    "location_jobs": ("location",),
    "scholarship": ("funding",),
    "flexibility": ("flexibility",),
    "brand_ranking": (),
}

# Which aspect each catalogue fact belongs to (program.facts columns).
FIELD_DIMENSION = {
    "application_fee": "cost",
    "duration_ft_months": "duration", "duration_pt_months": "duration", "max_candidature_months": "duration",
    "course_count": "duration", "total_credits": "duration",
    "capstone": "curriculum", "internship": "curriculum", "programming_prereq": "curriculum",
    "background_requirement": "admission", "gmat_gre_policy": "admission", "gmat_gre_note": "admission",
    "toefl_ibt_min": "admission", "toefl_ibt_band_min": "admission", "ielts_min": "admission",
    "ielts_sub_min": "admission", "english_waiver": "admission", "work_exp_policy": "admission",
    "work_exp_min_years": "admission", "cohort_size": "admission",
    "study_modes": "flexibility", "intake_months": "flexibility", "notes": "flexibility",
    "stem_designated": "location",
}

# Decision factors the catalogue holds no data for yet.
UNSUPPORTED_FACTORS = frozenset({"brand_ranking"})


def order(asked: list[str] | tuple[str, ...], factors: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if asked:
        return tuple(d for d in DEFAULT_ORDER if d in asked)
    first = [d for factor in factors for d in FACTOR_DIMENSIONS.get(factor, ())]
    return tuple(dict.fromkeys([*first, *DEFAULT_ORDER]))
