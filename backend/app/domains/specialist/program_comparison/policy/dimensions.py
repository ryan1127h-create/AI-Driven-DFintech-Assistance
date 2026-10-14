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

# Decision factors the catalogue holds no data for yet.
UNSUPPORTED_FACTORS = frozenset({"brand_ranking"})


def order(asked: list[str] | tuple[str, ...], factors: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if asked:
        return tuple(d for d in DEFAULT_ORDER if d in asked)
    first = [d for factor in factors for d in FACTOR_DIMENSIONS.get(factor, ())]
    return tuple(dict.fromkeys([*first, *DEFAULT_ORDER]))
