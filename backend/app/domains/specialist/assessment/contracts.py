"""The sole data boundary between the tools layer and the assessment.

The tools layer puts the applicant's facts (from the profile, plus what
the message itself states) and MSc DFT's checked admission requirements
(from the programme catalogue) into one report; the domain runs on that
report alone and never reads a profile store or the catalogue.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(max_length=100)]
LongText = Annotated[str, Field(max_length=1000)]

TestKey = Literal["GRE", "GMAT", "GATE", "TOEFL", "IELTS"]
# Where a fact came from: the profile (the user's own answer, or their CV)
# or the message being assessed.
FactSource = Literal["profile", "cv", "message"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TestScore(_Strict):
    """One admission test as the profile stores it (admission_tests)."""

    key: TestKey
    score: float | None = None
    test_date: date | None = None


class ApplicantFacts(_Strict):
    """The profile facts the assessment reads, by profile field key and in
    the profile's own values. Absent means not known — never "doesn't
    have it"."""

    highest_degree: ShortText | None = None
    degree_discipline_category: ShortText | None = None
    bachelor_grad_year: int | None = None
    gpa_band: ShortText | None = None
    english_medium_degree: bool | None = None
    admission_tests: list[TestScore] = Field(default_factory=list)
    code_level: int | None = Field(default=None, ge=0, le=4)
    math_stats_level: int | None = Field(default=None, ge=1, le=3)
    finance_level: int | None = Field(default=None, ge=1, le=3)
    tech_stack: list[ShortText] = Field(default_factory=list)
    prior_coursework: list[ShortText] = Field(default_factory=list)
    total_work_years: ShortText | None = None
    function_experience: list[ShortText] = Field(default_factory=list)
    research_output: ShortText | None = None
    certifications: list[ShortText] = Field(default_factory=list)
    intake_term: ShortText | None = None
    # field key -> where the value came from, for the facts that are known.
    sources: dict[str, FactSource] = Field(default_factory=dict)


class Requirements(_Strict):
    """MSc DFT's admission requirements for one intake, from the programme
    catalogue's checked record (each with the official page it follows)."""

    intake_year: int
    toefl_ibt_min: int | None = None
    toefl_band_min: float | None = None
    ielts_min: float | None = None
    gmat_gre_policy: ShortText | None = None
    # The GMAT score the FAQ says is generally expected, when it gives one.
    gmat_reference: int | None = None
    work_exp_policy: ShortText | None = None
    programming_prereq: ShortText | None = None
    background_requirement: LongText | None = None
    application_opens: date | None = None
    application_closes: date | None = None
    # requirement key -> official page.
    source_urls: dict[str, str] = Field(default_factory=dict)


class AssessmentReport(_Strict):
    facts: ApplicantFacts
    requirements: Requirements
    today: date
