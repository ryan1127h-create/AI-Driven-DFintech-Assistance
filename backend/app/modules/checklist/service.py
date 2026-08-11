"""Checklist contract service.

The real checklist engine will eventually read persisted application material
status. This service deliberately returns a stable API-shaped payload only, so
frontend and downstream module integration can start without pretending that
document tracking already exists.
"""

from __future__ import annotations

from app.modules.checklist.schemas import ChecklistResponse
from app.modules.profile.constants import TEST_USER_ID


_CONTRACT_ITEMS = [
    {
        "id": "personal_statement",
        "title": "Personal statement",
        "category": "admission_document",
        "requirement": "required",
    },
    {
        "id": "cv",
        "title": "Curriculum vitae / CV",
        "category": "admission_document",
        "requirement": "required",
    },
    {
        "id": "identity_document",
        "title": "Passport / NRIC / proof of residence",
        "category": "admission_document",
        "requirement": "required",
    },
    {
        "id": "degree_certificate",
        "title": "Degree certificate or expected graduation letter",
        "category": "admission_document",
        "requirement": "required",
    },
    {
        "id": "transcript",
        "title": "Official transcript",
        "category": "admission_document",
        "requirement": "required",
    },
    {
        "id": "english_proficiency",
        "title": "TOEFL / IELTS score report",
        "category": "test_score",
        "requirement": "conditional",
    },
    {
        "id": "standardised_test_scores",
        "title": "GRE / GMAT / GATE score report",
        "category": "test_score",
        "requirement": "recommended",
    },
    {
        "id": "referee_reports",
        "title": "Two referee reports",
        "category": "reference",
        "requirement": "required",
    },
    {
        "id": "financial_support",
        "title": "Financial support document",
        "category": "finance",
        "requirement": "optional",
    },
    {
        "id": "application_fee",
        "title": "Application fee payment proof",
        "category": "admission_document",
        "requirement": "required",
    },
]


def get_checklist(user_id: str = TEST_USER_ID) -> ChecklistResponse:
    items = [
        {
            **item,
            "status": "unknown",
            "owner": "student",
            "description": "Contract placeholder. Real status should be filled by the checklist engine.",
            "evidence_source": None,
            "blocking_fields": [],
        }
        for item in _CONTRACT_ITEMS
    ]
    return ChecklistResponse(
        user_id=user_id,
        lifecycle_stage=None,
        implementation_status="contract_only",
        items=items,
        outstanding_required_count=0,
        notes=[
            "This endpoint defines the checklist API shape only.",
            "It does not read or persist actual submitted document status yet.",
        ],
    )
