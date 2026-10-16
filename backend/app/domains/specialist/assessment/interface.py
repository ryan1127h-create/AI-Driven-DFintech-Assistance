"""
Public interface of the assessment domain — the only module other domains
(and the tools layer) are allowed to import from
app.domains.specialist.assessment.

The application readiness assessment for MSc DFT: the hard conditions an
application must meet (degree, programming or quantitative preparation,
English, applying in time) and the soft factors that decide how
competitive it is, each decided by code from the applicant's facts and the
programme's checked requirements — never an admission prediction. The
caller (app/tools/specialist/assessment/) assembles the report from the
profile, the message and the programme catalogue, and writes the reply;
this domain reads no data and makes no LLM call.

Usage:
    from app.domains.specialist.assessment import interface as assessment
    result = assessment.assess(report_dict)   # AssessmentResult.to_dict()
"""

from __future__ import annotations

from app.domains.specialist.assessment.contracts import AssessmentReport
from app.domains.specialist.assessment.workflow import assess as _assess

__all__ = ["assess", "AssessmentReport"]


def assess(report: dict | AssessmentReport) -> dict:
    """The assessment as a plain dict (see models.AssessmentResult).
    Raises pydantic.ValidationError on a malformed report."""
    model = report if isinstance(report, AssessmentReport) else AssessmentReport.model_validate(report)
    return _assess(model).to_dict()

