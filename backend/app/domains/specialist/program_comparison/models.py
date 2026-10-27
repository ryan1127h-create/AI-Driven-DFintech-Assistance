"""Internal domain models: what the stages hand one another. The workflow
builds them from the validated ComparisonInput; schemas.py turns the
final result into the response."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Applicant:
    """What is known about the applicant; None / empty means not known."""

    residency: str | None = None
    is_nus_alumnus: bool | None = None
    english_medium_degree: bool | None = None
    # ({key, score, test_date}, ...)
    tests: tuple[dict, ...] = ()
    work_band: str | None = None
    decision_factors: tuple[str, ...] = ()
    intake_year: int | None = None
    target_role: str | None = None
    target_skills: tuple[str, ...] = ()

    @property
    def known(self) -> bool:
        return any((self.residency, self.is_nus_alumnus is not None, self.english_medium_degree is not None,
                    self.tests, self.work_band, self.decision_factors, self.intake_year, self.target_skills))


@dataclass(frozen=True)
class Conditions:
    """explore's filter, as the message stated it."""

    countries: tuple[str, ...] = ()
    study_mode: str | None = None
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class Conflict:
    """A fact one official page states differently from the page followed."""

    field: str
    dimension: str
    followed_url: str | None
    other_url: str
    other_quote: str | None
    note: str


@dataclass(frozen=True)
class ProgramView:
    """S3: one programme's facts laid out by aspect, with where each came from."""

    program_id: str
    name: str
    short_name: str
    university_id: str
    university: str
    university_short: str
    city: str
    country_code: str
    country: str
    category: str
    is_target: bool
    intake_year: int
    official_url: str
    summary: str | None
    # dimension -> {fact: value}, only facts on file
    facts: dict[str, dict]
    # dimension -> source URLs
    sources: dict[str, tuple[str, ...]]
    conflicts: tuple[Conflict, ...]
    # The raw rows S4 reads.
    fees: tuple[dict, ...] = ()
    funding: tuple[dict, ...] = ()
    deadlines: tuple[dict, ...] = ()
    curriculum: tuple[dict, ...] = ()
    raw_facts: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicantFit:
    """S4: one programme read against the applicant, by aspect. An aspect
    is absent when nothing about the applicant bears on it."""

    program_id: str
    by_dimension: dict[str, dict]
    # The catalogue's facts are for another intake than the applicant's.
    intake_mismatch: bool = False


@dataclass(frozen=True)
class Contrast:
    """S6: one difference between MSc DFT and another programme, stated
    from the facts — never a judgement of which is better."""

    dimension: str
    program_id: str
    kind: str
    detail: dict


@dataclass(frozen=True)
class ComparisonResult:
    request_id: str
    mode: str
    today: date
    dimensions: tuple[str, ...]
    # MSc DFT (compare, explore), or the programme asked about (detail).
    baseline: dict | None
    subjects: tuple[dict, ...] = ()
    matches: tuple[dict, ...] = ()
    contrasts: tuple[Contrast, ...] = ()
    personalised: bool = False
    unsupported_factors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    # errors.WorkflowDiagnostic / errors.WorkflowStageResult
    diagnostics: tuple = ()
    stage_results: tuple = ()
