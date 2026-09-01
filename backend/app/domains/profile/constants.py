"""
Shared constants for the profile domain. Split into its own file (rather
than living in interface.py or service.py) so both can import it without
creating a circular dependency between them.
"""

# The columns extracted from a résumé / rendered into the chatbot prompt.
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

# Grounded in the live student.user_profiles CHECK constraints.
TECH_LEVEL_VALUES = ["none", "basic", "strong"]
TARGET_ROLE_VALUES = [
    "quant_risk", "data_analytics", "fintech_pm",
    "payments", "digital_banking", "compliance_regtech",
]
LIFECYCLE_VALUES = ["prospect", "applicant", "admitted", "enrolled", "alumni"]
ACADEMIC_BACKGROUND_VALUES = ["finance", "cs_computing", "engineering", "business", "other"]
