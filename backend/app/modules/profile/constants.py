"""
Shared constants for the profile module. Split into its own file (rather
than living in interface.py or service.py) so both can import it without
creating a circular dependency between them.
"""

# No login/auth exists yet — every profile read/write operates as this one
# placeholder identity. student.user_profiles.user_id is a foreign key to
# student.users(user_id), so a matching row was pre-seeded once via
# app/modules/profile/schema/seed_test_user.sql. Swapping this for a real
# per-request user id later is a one-line change here.
TEST_USER_ID = "55d56a67-4502-495d-b477-7db602850918"

# The columns extracted from a resume / rendered into the chatbot prompt.
# Kept as one source of truth for repository selects/upserts, the résumé
# extraction agent's prompt, and the API response schema.
PROFILE_FIELDS = [
    "lifecycle_stage",
    "academic_background_raw", "academic_background_std",
    "tech_level_raw", "tech_level_std",
    "school_tier", "work_years",
    "gmat", "gre", "toefl", "ielts",
    "target_role_raw", "target_role_std",
    "target_industry_raw", "target_industry_std",
    "application_term", "intake_year",
    "completed_courses",
]

# Grounded in the live student.user_profiles CHECK constraints (sandbox DB) —
# see app/modules/profile/schema/student_schema_clone.sql.
TECH_LEVEL_VALUES = ["none", "basic", "strong"]
TARGET_ROLE_VALUES = [
    "quant_risk", "data_analytics", "fintech_pm",
    "payments", "digital_banking", "compliance_regtech",
]
LIFECYCLE_VALUES = ["prospect", "applicant", "admitted", "enrolled", "alumni"]
