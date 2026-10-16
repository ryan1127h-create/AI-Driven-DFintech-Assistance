"""
S7 — the quick-fill card under an assessment for the profile fields still
unknown after the profile and the message were read (the domain's
missing_fields, most decisive first). Offered only when the whole profile
was read: without the consent a filled-in field stays invisible to the
assessment, and asking for it would loop.
"""

from __future__ import annotations

from app.tools.contracts import MissingInputField
from app.tools.quick_fill import supplement_card
from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched

REASON = "A couple more details would make this assessment more complete (optional)."

PROMPTS = {
    "degree_discipline_category": "What did you study for your degree?",
    "highest_degree": "What is your highest degree?",
    "english_medium_degree": "Was your degree taught mainly in English?",
    "admission_tests": "Any TOEFL / IELTS or GMAT / GRE scores (with the test date)?",
    "code_level": "How would you rate your programming?",
    "prior_coursework": "Which relevant courses have you taken (e.g. statistics, linear algebra, programming)?",
    "math_stats_level": "How would you rate your maths and statistics?",
    "finance_level": "How would you rate your finance knowledge?",
    "function_experience": "What kind of work, internship or research have you done?",
    "total_work_years": "How many years of full-time work do you have?",
    "gpa_band": "Roughly where do your grades sit (e.g. first class, second upper)?",
}


def card(missing_fields: list[str] | tuple[str, ...], prefetched: Prefetched) -> dict | None:
    if not prefetched.profile_read:
        return None
    items = [MissingInputField(slot=key, prompt=PROMPTS[key], field_key=key, level="supplementary")
             for key in missing_fields if key in PROMPTS]
    return supplement_card(items, REASON)
