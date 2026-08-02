"""Synthetic user/application data for experiments and tests.

Provides a handful of diverse, deterministic profiles spanning backgrounds,
target roles, and lifecycle stages so each agent can be demoed and tested
without real systems.
"""
from __future__ import annotations

from .profile import (
    AcademicBackground,
    Application,
    ApplicationType,
    ConsentFlags,
    DegreeClassification,
    DegreeLevel,
    DocStatus,
    FieldOfStudy,
    LearningStyle,
    LifecycleStage,
    NotificationChannel,
    NotificationFrequency,
    NotificationPrefs,
    Proficiency,
    StatusCode,
    StatusEvent,
    TargetRole,
    UserProfile,
    WorkDomain,
)

# Deterministic library of mock profiles keyed by a short id.
_PROFILES: dict[str, UserProfile] = {
    # CS grad + 2y banking, applying full-time, aiming fintech PM.
    "1": UserProfile(
        user_id="u_0001",
        lifecycle_stage=LifecycleStage.applicant,
        authenticated=True,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.computer_science,
            institution="Overseas University",
            graduation_year=2022,
        ),
        work_years=2,
        work_domain=WorkDomain.banking,
        country="IN",
        technical_proficiency=Proficiency.intermediate,
        finance_knowledge=Proficiency.basic,
        target_roles=[TargetRole.fintech_pm, TargetRole.quant_risk],
        preferred_learning_style=LearningStyle.structured,
        application_type=ApplicationType.full_time,
        completed_modules=["BMD5301"],  # exercises #7 prereq + progress
        application=Application(
            application_id="app_0001",
            status_code=StatusCode.UNDER_REVIEW,
            submitted_documents=["cv", "degree_certificate"],
            deadlines={"offer_acceptance": "2026-07-15"},
        ),
        consent_flags=ConsentFlags(personalization=True, reminders=True),
    ),
    # Finance grad, no work experience, prospect exploring fit.
    "2": UserProfile(
        user_id="u_0002",
        lifecycle_stage=LifecycleStage.prospect,
        authenticated=False,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.finance,
            graduation_year=2025,
        ),
        work_years=0,
        work_domain=WorkDomain.none,
        country="SG",
        technical_proficiency=Proficiency.basic,
        finance_knowledge=Proficiency.advanced,
        target_roles=[TargetRole.compliance_regtech, TargetRole.digital_banking],
        preferred_learning_style=LearningStyle.exploratory,
        application_type=ApplicationType.full_time,
        consent_flags=ConsentFlags(personalization=True),
    ),
    # Local engineering grad, part-time applicant, docs missing.
    "3": UserProfile(
        user_id="u_0003",
        lifecycle_stage=LifecycleStage.applicant,
        authenticated=True,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.engineering,
            institution="National University of Singapore",
            graduation_year=2019,
        ),
        work_years=5,
        work_domain=WorkDomain.tech,
        country="SG",
        technical_proficiency=Proficiency.advanced,
        finance_knowledge=Proficiency.none,
        target_roles=[TargetRole.payments, TargetRole.data_analytics],
        preferred_learning_style=LearningStyle.structured,
        application_type=ApplicationType.part_time,
        application=Application(
            application_id="app_0003",
            status_code=StatusCode.DOCS_REQUIRED,
            submitted_documents=["cv"],
            deadlines={"document_deadline": "2026-06-10"},
        ),
        consent_flags=ConsentFlags(personalization=True, reminders=True),
    ),
    # Overseas applicant exercising Checklist v2: low classification (triggers
    # academic justification), mixed document statuses, and a near application
    # deadline (for urgency). Used by #4 v2 tests/demos.
    "4": UserProfile(
        user_id="u_0004",
        lifecycle_stage=LifecycleStage.applicant,
        authenticated=True,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.business,
            institution="Overseas University",
            graduation_year=2023,
            degree_classification=DegreeClassification.second_lower,  # below 2:1
        ),
        work_years=1,
        work_domain=WorkDomain.consulting,
        country="MY",
        technical_proficiency=Proficiency.basic,
        finance_knowledge=Proficiency.intermediate,
        target_roles=[TargetRole.fintech_pm],
        application_type=ApplicationType.full_time,
        application=Application(
            application_id="app_0004",
            status_code=StatusCode.DOCS_REQUIRED,
            submitted_documents=["cv", "personal_statement"],
            document_status={
                "cv": DocStatus.verified,
                "personal_statement": DocStatus.under_review,
                "transcript": DocStatus.rejected,  # needs re-submission
            },
            deadlines={"application_deadline": "2026-06-03"},
            status_history=[
                StatusEvent(status_code=StatusCode.SUBMITTED, date="2026-05-10"),
                StatusEvent(status_code=StatusCode.UNDER_REVIEW, date="2026-05-15"),
                StatusEvent(status_code=StatusCode.DOCS_REQUIRED, date="2026-05-25",
                            note="Transcript was rejected and must be resubmitted"),
            ],
        ),
        email="demo.applicant@example.com",
        consent_flags=ConsentFlags(personalization=True, reminders=True),
        notification_prefs=NotificationPrefs(
            channels=[NotificationChannel.in_app, NotificationChannel.email],
            frequency=NotificationFrequency.immediate,
        ),
    ),
    # Current student targeting fintech PM — exercises completed-course awareness.
    # completed_modules: 2 real fintech_pm modules (BMS5312, FT5001) + 1 typo
    # (ZZZ000) to demo unrecognised-code handling (path E in the spec).
    "6": UserProfile(
        user_id="u_0006",
        lifecycle_stage=LifecycleStage.current,
        authenticated=True,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.finance,
            institution="National University of Singapore",
            graduation_year=2023,
        ),
        work_years=1,
        work_domain=WorkDomain.fintech,
        country="SG",
        technical_proficiency=Proficiency.intermediate,
        finance_knowledge=Proficiency.intermediate,
        target_roles=[TargetRole.fintech_pm],
        preferred_learning_style=LearningStyle.structured,
        application_type=ApplicationType.full_time,
        completed_modules=["BMS5312", "FT5001", "ZZZ000"],
        application=None,
        consent_flags=ConsentFlags(personalization=True, reminders=True),
    ),
    # FULLY-POPULATED applicant — exercises every v2 feature across #4-#7.
    # Persona: Aisha Rahman, overseas CS grad (2:1), 3y fintech, full-time
    # applicant, currently DOCS_REQUIRED (transcript rejected).
    "5": UserProfile(
        user_id="u_0005",
        lifecycle_stage=LifecycleStage.applicant,
        authenticated=True,
        academic_background=AcademicBackground(
            degree_level=DegreeLevel.bachelor,
            field_of_study=FieldOfStudy.computer_science,
            institution="University of Delhi",
            graduation_year=2021,
            degree_classification=DegreeClassification.second_upper,
        ),
        work_years=3,
        work_domain=WorkDomain.fintech,
        country="IN",
        technical_proficiency=Proficiency.advanced,
        finance_knowledge=Proficiency.intermediate,
        target_roles=[TargetRole.fintech_pm, TargetRole.payments],
        preferred_learning_style=LearningStyle.structured,
        application_type=ApplicationType.full_time,
        completed_modules=["BMD5301", "BMF5324"],  # prior/exempted credits
        application=Application(
            application_id="app_0005",
            status_code=StatusCode.DOCS_REQUIRED,
            submitted_documents=["cv", "personal_statement", "degree_certificate"],
            document_status={
                "cv": DocStatus.verified,
                "degree_certificate": DocStatus.verified,
                "personal_statement": DocStatus.under_review,
                "transcript": DocStatus.rejected,
            },
            deadlines={
                "application_deadline": "2026-06-05",
                "offer_acceptance": "2026-07-20",
            },
            status_history=[
                StatusEvent(status_code=StatusCode.SUBMITTED, date="2026-05-08"),
                StatusEvent(status_code=StatusCode.UNDER_REVIEW, date="2026-05-12"),
                StatusEvent(status_code=StatusCode.DOCS_REQUIRED, date="2026-05-22",
                            note="Transcript was not clear enough and must be reuploaded"),
            ],
        ),
        email="demo.applicant@example.com",
        consent_flags=ConsentFlags(
            personalization=True, reminders=True, alumni_matching=True
        ),
        notification_prefs=NotificationPrefs(
            channels=[NotificationChannel.in_app, NotificationChannel.email],
            frequency=NotificationFrequency.immediate,
        ),
    ),
}


def get_profile(profile_id: str) -> UserProfile:
    """Return a copy of a named mock profile."""
    if profile_id not in _PROFILES:
        raise KeyError(
            f"unknown mock profile {profile_id!r}; available: {list(_PROFILES)}"
        )
    return _PROFILES[profile_id].model_copy(deep=True)
