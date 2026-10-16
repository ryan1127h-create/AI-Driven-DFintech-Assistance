"""
Tunable career-planning parameters — fit weights, presentation sizes and
roadmap spacing. Unlike skill_evidence.py and calendar.py, every value
here is a design choice that can be adjusted without any rule changing.
Change them here only; the stages read them.
"""

from __future__ import annotations

# S4 role fit (stages/s4_fit): a role's fit is the mean evidence of its
# required skills (each capped at 1.0), plus this bonus when the student's
# functional experience is in the role's line of work.
FUNCTION_AFFINITY_BONUS = 0.15
# function_experience key -> the role families it is direct experience of.
FUNCTION_ROLE_AFFINITY: dict[str, frozenset[str]] = {
    "engineering": frozenset({"software_engineering", "data_engineering"}),
    "data_ai": frozenset({"data_analytics", "machine_learning_ai"}),
    "quant": frozenset({"quantitative_finance"}),
    "risk_compliance": frozenset({"risk_management", "regulation_governance"}),
    "product_business": frozenset({"product_business", "entrepreneurship"}),
}
# A fit resting mostly on skills with no evidence either way is flagged
# low-confidence: above this share of the role's skills unknown.
LOW_CONFIDENCE_UNKNOWN_SHARE = 0.5

# S6 exploration: how many roles to put forward.
EXPLORATION_TOP_N = 4
# S6 compare: the most roles one comparison holds.
COMPARE_MAX_ROLES = 3

# S5 roadmap: a job search "right after" graduating starts this many
# months before the graduation term ends and runs this many after it.
JOB_SEARCH_LEAD_MONTHS = 4
JOB_SEARCH_TAIL_MONTHS = 3
# At most this many skill gaps are worked on in one phase.
MAX_GAPS_PER_PHASE = 3
