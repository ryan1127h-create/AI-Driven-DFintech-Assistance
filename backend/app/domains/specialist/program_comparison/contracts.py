"""The sole data boundary between the upstream agent and programme comparison.

The upstream agent (the tools layer) places the programme catalogue (NUS
MSc DFT and the programmes it is compared with, verified facts only), the
applicant's own situation and what the message asked for in one report;
the domain runs on that report alone and never reads the catalogue or a
profile store.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SchemaVersion = Literal["1.0"]
# compare: MSc DFT against one to three named programmes; detail: the facts
# of one programme; explore: which catalogue programmes meet the stated
# conditions (a filter, never a ranking).
Mode = Literal["compare", "detail", "explore"]
# The aspects a comparison is laid out by.
Dimension = Literal["cost", "duration", "curriculum", "admission", "flexibility", "funding", "deadlines", "location"]
# profile decision_factors
DecisionFactor = Literal[
    "brand_ranking", "cost", "duration", "tech_depth", "finance_depth", "location_jobs", "scholarship", "flexibility",
]
Residency = Literal["sg_citizen", "sg_pr", "international"]
StudyMode = Literal["full_time", "part_time", "online"]
Category = Literal["fintech", "quant_finance", "financial_engineering", "finance", "business_analytics", "computing"]
# The skill vocabulary of the knowledge base's role tags
# (knowledge.tags_definition.required_skills).
SkillId = Literal[
    "ai_ml", "data_analytics", "data_engineering", "finance", "payments_systems",
    "product", "programming", "regulation", "risk_modeling", "security",
]
Coverage = Literal["required", "core_option", "elective", "none"]
TestKey = Literal["GRE", "GMAT", "GATE", "TOEFL", "IELTS"]
StudentCategory = Literal["all", "domestic", "international"]
EligibleCategory = Literal["all", "sg_citizen", "sg_pr", "domestic", "international", "alumni"]

ShortText = Annotated[str, Field(max_length=100)]
LongText = Annotated[str, Field(max_length=500)]
Url = Annotated[str, Field(max_length=2048)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class _StrictInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _deduplicate(values: list) -> list:
    return list(dict.fromkeys(value for value in values if value))


# ── the catalogue ─────────────────────────────────────────────────────────

class SourceInput(_StrictInputModel):
    """Where one fact came from: 'primary' is the page the value follows,
    'conflicting' one that says otherwise, with how that was decided."""

    source_url: Url
    quote: Annotated[str, Field(max_length=500)] | None = None
    role: Literal["primary", "conflicting"] = "primary"
    note: LongText | None = None


class UniversityInput(_StrictInputModel):
    university_id: ShortText
    name: LongText
    short_name: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    city: ShortText
    country_code: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    country_name: ShortText


class ProgramFactsInput(_StrictInputModel):
    """A programme's facts for one intake (program.facts); absent means
    not published — never "doesn't have it"."""

    intake_months: list[int] = Field(default_factory=list, max_length=12)
    study_modes: list[StudyMode] = Field(default_factory=list, max_length=3)
    duration_ft_months: float | None = Field(default=None, gt=0)
    duration_pt_months: float | None = Field(default=None, gt=0)
    max_candidature_months: float | None = Field(default=None, gt=0)
    course_count: int | None = Field(default=None, gt=0)
    total_credits: float | None = Field(default=None, gt=0)
    credit_unit: ShortText | None = None
    capstone: Literal["required", "optional", "none"] | None = None
    internship: Literal["required", "optional", "none"] | None = None
    application_fee: float | None = Field(default=None, ge=0)
    application_fee_currency: Currency | None = None
    gmat_gre_policy: Literal["required", "required_waivable", "recommended", "optional", "not_considered"] | None = None
    gmat_gre_note: LongText | None = None
    toefl_ibt_min: int | None = Field(default=None, ge=0, le=120)
    toefl_ibt_band_min: float | None = Field(default=None, ge=1, le=6)
    ielts_min: float | None = Field(default=None, ge=0, le=9)
    ielts_sub_min: float | None = Field(default=None, ge=0, le=9)
    english_waiver: LongText | None = None
    work_exp_policy: Literal["required", "preferred", "not_required"] | None = None
    work_exp_min_years: float | None = Field(default=None, ge=0)
    programming_prereq: Literal["required", "conditional", "recommended", "not_required"] | None = None
    background_requirement: LongText | None = None
    stem_designated: bool | None = None
    cohort_size: int | None = Field(default=None, gt=0)
    notes: LongText | None = None

    @field_validator("intake_months")
    @classmethod
    def validate_months(cls, value: list[int]) -> list[int]:
        if any(not 1 <= month <= 12 for month in value):
            raise ValueError("intake months are 1-12")
        return sorted(set(value))


class FeeInput(_StrictInputModel):
    student_category: StudentCategory
    amount: float = Field(ge=0)
    currency: Currency
    basis: Literal["programme", "per_year", "per_credit"]
    includes_tax: bool | None = None
    note: LongText | None = None
    source_url: Url
    quote: Annotated[str, Field(max_length=500)] | None = None


class DeadlineInput(_StrictInputModel):
    round_no: int = Field(gt=0)
    applicant_category: StudentCategory = "all"
    round_label: ShortText | None = None
    opens_on: date | None = None
    closes_on: date
    source_url: Url

    @model_validator(mode="after")
    def validate_order(self) -> "DeadlineInput":
        if self.opens_on and self.opens_on > self.closes_on:
            raise ValueError("a round cannot open after it closes")
        return self


class FundingInput(_StrictInputModel):
    funding_id: ShortText
    name: LongText
    kind: Literal["scholarship", "rebate", "grant", "subsidy", "loan"]
    amount_kind: Literal["fixed", "percent_tuition", "full_tuition", "varies"]
    amount: float | None = Field(default=None, ge=0)
    currency: Currency | None = None
    percent: float | None = Field(default=None, gt=0, le=100)
    # None: the source doesn't say who may receive it.
    eligible_categories: list[EligibleCategory] | None = None
    bond_required: bool | None = None
    conditions: LongText | None = None
    valid_from_year: int | None = None
    valid_to_year: int | None = None
    source_url: Url


class CurriculumAreaInput(_StrictInputModel):
    skill_id: SkillId
    coverage: Coverage
    evidence_courses: list[LongText] = Field(default_factory=list, max_length=20)
    source_url: Url | None = None


class ProgramInput(_StrictInputModel):
    """One catalogue programme (program_catalog.list_programs())."""

    program_id: ShortText
    name: LongText
    short_name: ShortText
    faculty: LongText | None = None
    degree_type: ShortText
    category: Category
    is_target: bool = False
    aliases: list[ShortText] = Field(default_factory=list, max_length=20)
    official_url: Url
    delivery: Literal["on_campus", "online", "hybrid"] = "on_campus"
    summary: LongText | None = None
    intake_year: int = Field(ge=2024, le=2035)
    verified_at: date | None = None
    university: UniversityInput
    facts: ProgramFactsInput = Field(default_factory=ProgramFactsInput)
    sources: dict[str, list[SourceInput]] = Field(default_factory=dict)
    fees: list[FeeInput] = Field(default_factory=list, max_length=10)
    deadlines: list[DeadlineInput] = Field(default_factory=list, max_length=12)
    funding: list[FundingInput] = Field(default_factory=list, max_length=30)
    curriculum: list[CurriculumAreaInput] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_programme(self) -> "ProgramInput":
        skills = [area.skill_id for area in self.curriculum]
        if len(skills) != len(set(skills)):
            raise ValueError(f"{self.program_id}: a skill appears twice in its curriculum")
        categories = [fee.student_category for fee in self.fees]
        if len(categories) != len(set(categories)):
            raise ValueError(f"{self.program_id}: two fees for the same student category")
        return self


# ── the applicant ─────────────────────────────────────────────────────────

class AdmissionTestInput(_StrictInputModel):
    """One admission test on file (profile admission_tests). A TOEFL
    score of 6 or below is on the 1-6 scale used from 21 January 2026."""

    key: TestKey
    score: float | None = Field(default=None, ge=0)
    test_date: date | None = None


class ApplicantInput(_StrictInputModel):
    """What the profile ("adm" purpose, consent-filtered) and the message
    say about the applicant. Absent means not known."""

    residency: Residency | None = None
    is_nus_alumnus: bool | None = None
    english_medium_degree: bool | None = None
    tests: list[AdmissionTestInput] = Field(default_factory=list, max_length=10)
    total_work_years: Literal["0", "<1", "1-3", "3-5", "5-10", "10+"] | None = None
    decision_factors: list[DecisionFactor] = Field(default_factory=list, max_length=8)
    # The academic year they mean to start (AY2027/28 -> 2027).
    intake_year: int | None = Field(default=None, ge=2024, le=2035)
    target_role: LongText | None = None
    target_skills: list[SkillId] = Field(default_factory=list, max_length=10)

    @field_validator("decision_factors", "target_skills")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)


class ConditionsInput(_StrictInputModel):
    """Conditions the message states, for explore."""

    countries: list[Annotated[str, Field(pattern=r"^[A-Z]{2}$")]] = Field(default_factory=list, max_length=10)
    study_mode: StudyMode | None = None
    categories: list[Category] = Field(default_factory=list, max_length=6)


# ── the report ────────────────────────────────────────────────────────────

class ComparisonInput(_StrictInputModel):
    """The only object the programme-comparison domain may consume."""

    schema_version: SchemaVersion = "1.0"
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=100)
    # Correlation metadata only; never used to look anything up.
    user_id: str | None = Field(default=None, min_length=1, max_length=100)
    mode: Mode
    # The date deadlines are judged against.
    today: date
    programs: list[ProgramInput] = Field(min_length=1, max_length=60)
    # The programmes the request is about: compare 1-3 others (MSc DFT is
    # always the baseline, never listed here); detail exactly one (may be
    # MSc DFT); explore none (it considers the whole catalogue).
    subject_ids: list[ShortText] = Field(default_factory=list, max_length=3)
    # Aspects the message asked about; empty lets the decision factors (or
    # the default order) decide.
    dimensions: list[Dimension] = Field(default_factory=list, max_length=8)
    applicant: ApplicantInput = Field(default_factory=ApplicantInput)
    conditions: ConditionsInput = Field(default_factory=ConditionsInput)
    # The user asked which programme suits them (compare only): the result
    # then checks each programme against their own goals (stages/s5_goals).
    asks_which_suits: bool = False

    @field_validator("subject_ids", "dimensions")
    @classmethod
    def deduplicate(cls, value: list[str]) -> list[str]:
        return _deduplicate(value)

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "ComparisonInput":
        ids = [p.program_id for p in self.programs]
        if len(ids) != len(set(ids)):
            raise ValueError("programs contains duplicate program ids")
        targets = [p.program_id for p in self.programs if p.is_target]
        if len(targets) != 1:
            raise ValueError("programs must contain exactly one target programme (MSc DFT)")
        unknown = [s for s in self.subject_ids if s not in set(ids)]
        if unknown:
            raise ValueError("subjects not in programs: " + ", ".join(unknown))

        count = len(self.subject_ids)
        if self.mode == "compare":
            if not 1 <= count <= 3:
                raise ValueError("a comparison is MSc DFT against one to three programmes")
            if targets[0] in self.subject_ids:
                raise ValueError("MSc DFT is the comparison's baseline, not a subject")
        if self.mode == "detail" and count != 1:
            raise ValueError("detail is about exactly one programme")
        if self.mode == "explore" and count:
            raise ValueError("explore considers the whole catalogue; subject_ids must be empty")
        return self
