"""
The assessment, end to end: the hard conditions, the soft factors, then
the verdict, the strengths and the two most worthwhile improvements, and
the profile fields still worth asking for. Pure computation on the report
— the same facts always give the same assessment.
"""

from __future__ import annotations

from app.domains.specialist.assessment import policy
from app.domains.specialist.assessment.contracts import AssessmentReport, ApplicantFacts
from app.domains.specialist.assessment.models import AssessmentResult, HardCheck, SoftFactor
from app.domains.specialist.assessment.stages import hard, soft

MAX_IMPROVEMENTS = 2
MAX_MISSING_FIELDS = 3

# Soft factors in the order they are worth strengthening: what the
# programme asks most directly of every applicant first, optional tests last.
_IMPROVEMENT_ORDER = ("programming_depth", "relevant_experience", "quant_foundation", "finance_foundation",
                      "background_fit", "academic_record", "test_scores")


def _verdict(checks: tuple[HardCheck, ...]) -> str:
    statuses = {c.status for c in checks}
    if "gap" in statuses:
        return "gap"
    return "to_confirm" if "to_confirm" in statuses else "all_met"


def _applicant_type(facts: ApplicantFacts, this_year: int) -> str:
    if facts.total_work_years is not None:
        return "fresh_graduate" if facts.total_work_years in policy.NO_WORK else "experienced"
    if facts.bachelor_grad_year is not None:
        return "fresh_graduate" if facts.bachelor_grad_year >= this_year - 1 else "experienced"
    return "unknown"


def _missing(checks: tuple[HardCheck, ...], factors: tuple[SoftFactor, ...]) -> tuple[str, ...]:
    """The fields that would settle an open hard condition first (the
    decisive ones in policy order), then those an unknown soft factor
    needs."""
    hard_fields = list(dict.fromkeys(f for c in checks if c.status == "to_confirm" for f in c.missing_fields))
    soft_fields = [f for s in factors if s.status == "unknown" for f in s.missing_fields]
    ordered = [f for f in policy.DECISIVE_FIELDS if f in hard_fields]
    ordered += [f for f in hard_fields if f not in ordered]
    ordered += [f for f in soft_fields if f not in ordered]
    return tuple(ordered[:MAX_MISSING_FIELDS])


def assess(report: AssessmentReport) -> AssessmentResult:
    facts, req, today = report.facts, report.requirements, report.today
    # Scores must be valid when the application goes in.
    deadline = req.application_closes if req.application_closes and req.application_closes >= today else today
    checks = (
        hard.degree(facts),
        hard.programming_or_quant(facts),
        hard.english(facts, req, deadline),
        hard.timing(req, today),
    )
    factors = (
        soft.background_fit(facts),
        soft.programming_depth(facts),
        soft.quant_foundation(facts),
        soft.finance_foundation(facts),
        soft.relevant_experience(facts),
        soft.academic_record(facts),
        soft.test_scores(facts, req),
    )
    by_key = {f.key: f for f in factors}
    # Programming below the bar is the hard condition's to fix, not also a
    # competitive improvement.
    covered = {"programming_depth"} if checks[1].status in ("gap", "to_confirm") else set()
    improvements = tuple(k for k in _IMPROVEMENT_ORDER
                         if by_key[k].status == "improve" and k not in covered)[:MAX_IMPROVEMENTS]
    return AssessmentResult(
        verdict=_verdict(checks),
        hard=checks,
        soft=factors,
        applicant_type=_applicant_type(facts, today.year),
        strengths=tuple(f.key for f in factors if f.status == "strength"),
        improvements=improvements,
        missing_fields=_missing(checks, factors),
        intake_year=req.intake_year,
        application_opens=req.application_opens.isoformat() if req.application_opens else None,
        application_closes=req.application_closes.isoformat() if req.application_closes else None,
        fact_sources=dict(facts.sources),
    )
