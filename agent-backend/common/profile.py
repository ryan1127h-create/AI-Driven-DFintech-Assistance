"""Unified user profile model.

Implements the schema defined in docs/01-user-profile-schema.md. All four
agents (#4-#7) consume this model and nothing else for user data.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------- Enums (controlled vocabularies, schema doc §3) ----------
class LifecycleStage(str, Enum):
    prospect = "prospect"
    applicant = "applicant"
    admitted = "admitted"
    current = "current"
    graduating = "graduating"
    alumni = "alumni"


class DegreeLevel(str, Enum):
    high_school = "high_school"
    bachelor = "bachelor"
    master = "master"
    phd = "phd"


class FieldOfStudy(str, Enum):
    computer_science = "computer_science"
    finance = "finance"
    economics = "economics"
    engineering = "engineering"
    mathematics = "mathematics"
    business = "business"
    other = "other"


class DegreeClassification(str, Enum):
    """Honours classification, best to worst (see engine ordering)."""

    first = "first"
    second_upper = "second_upper"
    second_lower = "second_lower"
    third = "third"
    pass_ = "pass"
    unknown = "unknown"


class DocStatus(str, Enum):
    missing = "missing"
    submitted = "submitted"
    under_review = "under_review"
    verified = "verified"
    rejected = "rejected"


class NotificationChannel(str, Enum):
    in_app = "in_app"
    email = "email"


class NotificationFrequency(str, Enum):
    immediate = "immediate"
    daily_digest = "daily_digest"
    off = "off"


class WorkDomain(str, Enum):
    banking = "banking"
    tech = "tech"
    consulting = "consulting"
    fintech = "fintech"
    other = "other"
    none = "none"


class Proficiency(str, Enum):
    none = "none"
    basic = "basic"
    intermediate = "intermediate"
    advanced = "advanced"


class TargetRole(str, Enum):
    """MVP-supported roles (schema doc §3.2). Drives #6 and #7."""

    fintech_pm = "fintech_pm"
    quant_risk = "quant_risk"
    digital_banking = "digital_banking"
    payments = "payments"
    compliance_regtech = "compliance_regtech"
    data_analytics = "data_analytics"


class ApplicationType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"


class LearningStyle(str, Enum):
    structured = "structured"
    exploratory = "exploratory"


class StatusCode(str, Enum):
    """Raw application status codes (schema doc §3.3); #5 translates these."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DOCS_REQUIRED = "DOCS_REQUIRED"
    OFFER = "OFFER"
    WAITLIST = "WAITLIST"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


# ---------- Sub-objects ----------
class AcademicBackground(BaseModel):
    degree_level: DegreeLevel
    field_of_study: FieldOfStudy
    institution: str | None = None
    graduation_year: int | None = None
    degree_classification: DegreeClassification | None = None


class StatusEvent(BaseModel):
    """One entry in an application's status history timeline."""

    status_code: StatusCode
    date: str  # ISO date
    note: str | None = None


class Application(BaseModel):
    """#5 may write; other agents read-only."""

    application_id: str
    status_code: StatusCode
    submitted_documents: list[str] = Field(default_factory=list)
    # Optional richer per-document status (code -> DocStatus). Takes precedence
    # over submitted_documents when present.
    document_status: dict[str, DocStatus] = Field(default_factory=dict)
    deadlines: dict[str, str] = Field(default_factory=dict)  # name -> ISO date
    status_history: list[StatusEvent] = Field(default_factory=list)


class ConsentFlags(BaseModel):
    # Personalization is OPT-IN. The rag-data pipeline carries the inverse
    # switch (`personalization_opt_out`, default false = personalization on);
    # negating it is the adapter's job, not this model's -- do not flip this
    # default to accommodate that field.
    personalization: bool = False  # privacy-safe default (schema doc §5)
    reminders: bool = False
    alumni_matching: bool = False


class NotificationPrefs(BaseModel):
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.in_app]
    )
    frequency: NotificationFrequency = NotificationFrequency.immediate
    muted_milestones: list[str] = Field(default_factory=list)  # milestone keys to suppress


class NotificationRecord(BaseModel):
    """One dispatched-notification record, carried on the profile for dedup + audit."""

    key: str            # reminder key, e.g. "offer_acceptance:2026-07-15"
    date: str           # ISO date dispatched
    channels: list[str] = Field(default_factory=list)
    delivered: bool = True   # False if a real send failed (record kept for dedup)


# Any four-digit calendar year. Deliberately NOT a moving window around the
# current year: a hardcoded 2025-2027 range would silently expire and need a
# code change every intake. This only rejects nonsense like `25` or `226`.
MIN_INTAKE_YEAR = 1000
MAX_INTAKE_YEAR = 9999


# ---------- Root ----------
class UserProfile(BaseModel):
    user_id: str
    lifecycle_stage: LifecycleStage
    authenticated: bool = False
    email: str | None = None  # recipient address for the email channel

    academic_background: AcademicBackground | None = None
    work_years: int | None = None
    work_domain: WorkDomain | None = None
    country: str | None = None  # ISO 3166-1 alpha-2

    technical_proficiency: Proficiency | None = None
    finance_knowledge: Proficiency | None = None

    target_roles: list[TargetRole] = Field(default_factory=list)
    preferred_learning_style: LearningStyle | None = None
    application_type: ApplicationType | None = None
    completed_modules: list[str] = Field(default_factory=list)  # module codes done

    application: Application | None = None
    consent_flags: ConsentFlags = Field(default_factory=ConsentFlags)
    notification_prefs: NotificationPrefs = Field(default_factory=NotificationPrefs)
    notification_log: list[NotificationRecord] = Field(default_factory=list)

    # ---- Fields owned by the rag-data extraction pipeline ----
    # Source: rag-data/docs/user_profile_schema.md (that pipeline is read-only
    # for us). Every field here is optional with a safe default, so all callers
    # written before this block keep working unchanged.

    # Selects the right cohort in the retrieval side's `course_rules.intake`.
    # A plain int (not an enum of 2025/2026/2027) so a new intake needs no edit.
    intake_year: int | None = Field(default=None, ge=MIN_INTAKE_YEAR, le=MAX_INTAKE_YEAR)
    application_term: str | None = None  # free text, e.g. "2026 Fall"

    # Admission test scores. Stored exactly as reported -- never converted
    # between scales. `ge=0` is the only bound: real score ranges (GMAT Focus
    # vs classic, etc.) change, and guessing one here would be fabricated data.
    gmat: int | None = Field(default=None, ge=0)
    gre: int | None = Field(default=None, ge=0)
    toefl: int | None = Field(default=None, ge=0)
    # IELTS is reported in half bands (6.5, 7.0). An int would truncate 6.5 -> 6.
    ielts: float | None = Field(default=None, ge=0)

    asked_topics: list[str] = Field(default_factory=list)  # intent labels already asked
    updated_at: str | None = None  # ISO 8601 timestamp, same convention as StatusEvent.date

    # Record-only for now (rag-data doc §六 defers both to their v2). Left as
    # free text because no controlled vocabulary has been agreed for them yet.
    school_tier: str | None = None
    target_industry: str | None = None

    # The user's own wording, keyed by the field of THIS model it was mapped
    # into, e.g. {"technical_proficiency": "会一点 Python"}. The rag-data schema
    # stores {raw, std} pairs and its settings page shows `raw` back to the
    # user; keeping one dict here preserves that wording losslessly without
    # adding a parallel `*_raw` column per field or weakening any type above.
    # Values are display-only: never route them into retrieval or matching.
    raw_inputs: dict[str, str] = Field(default_factory=dict)
