"""Checklist service.

This is the R5-A backend foundation: static checklist definitions plus
per-user persisted state. It still does not inspect uploaded files by itself;
a future document-upload flow can update these item states through the same
repository/API.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from psycopg import errors

from app.modules.checklist import repository
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

_VALID_ITEM_IDS = {item["id"] for item in _CONTRACT_ITEMS}
_SUPPORTED_SUFFIXES = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def get_checklist(user_id: str = TEST_USER_ID) -> ChecklistResponse:
    states: dict[str, dict] = {}
    implementation_status = "partial"
    notes = [
        "Checklist state is persisted per user.",
        "Document upload and automatic verification are not connected yet.",
    ]

    try:
        states = repository.list_items(user_id)
    except (errors.UndefinedTable, errors.UndefinedColumn):
        implementation_status = "contract_only"
        notes = [
            "Checklist persistence table is not available. Run the R5 migration before using persisted status.",
            "The response is falling back to static checklist definitions.",
        ]

    items = [
        {
            **item,
            "status": states.get(item["id"], {}).get("status", "not_started"),
            "owner": "student",
            "description": "Preparation item for MSc DFT application materials.",
            "evidence_source": states.get(item["id"], {}).get("evidence_source"),
            "blocking_fields": [],
            "note": states.get(item["id"], {}).get("note"),
            "file_name": states.get(item["id"], {}).get("file_name"),
            "content_type": states.get(item["id"], {}).get("content_type"),
            "file_size": states.get(item["id"], {}).get("file_size"),
            "uploaded_at": states.get(item["id"], {}).get("uploaded_at"),
            "updated_at": states.get(item["id"], {}).get("updated_at"),
        }
        for item in _CONTRACT_ITEMS
    ]
    outstanding_required_count = sum(
        1
        for item in items
        if item["requirement"] == "required"
        and item["status"] not in {"completed", "not_applicable"}
    )
    return ChecklistResponse(
        user_id=user_id,
        lifecycle_stage=None,
        implementation_status=implementation_status,
        items=items,
        outstanding_required_count=outstanding_required_count,
        notes=notes,
    )


def patch_checklist_item(item_id: str, fields: dict, user_id: str = TEST_USER_ID) -> ChecklistResponse:
    item_id = item_id.strip()
    if item_id not in _VALID_ITEM_IDS:
        raise ValueError(f"Unknown checklist item_id: {item_id}")
    if not fields:
        raise ValueError("No checklist fields provided.")

    try:
        repository.upsert_item(user_id, item_id, fields)
    except (errors.UndefinedTable, errors.UndefinedColumn) as exc:
        raise RuntimeError(
            "Checklist persistence table is missing. Run "
            "backend/app/modules/checklist/schema/application_checklist_items.sql first."
        ) from exc
    return get_checklist(user_id)


async def upload_checklist_file(
    item_id: str,
    file: UploadFile,
    user_id: str = TEST_USER_ID,
) -> ChecklistResponse:
    item_id = item_id.strip()
    if item_id not in _VALID_ITEM_IDS:
        raise ValueError(f"Unknown checklist item_id: {item_id}")
    if not file.filename:
        raise ValueError("Uploaded file must have a filename.")

    safe_name = _safe_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            "Unsupported file type. Supported types: "
            + ", ".join(sorted(_SUPPORTED_SUFFIXES))
        )

    content = await file.read()
    size = len(content)
    if size == 0:
        raise ValueError("Uploaded file is empty.")
    if size > _MAX_UPLOAD_BYTES:
        raise ValueError("Uploaded file is too large. Maximum size is 10 MB.")

    return patch_checklist_item(
        item_id,
        {
            "status": "completed",
            "evidence_source": f"uploaded:{safe_name}",
            "file_name": safe_name,
            "content_type": file.content_type,
            "file_size": size,
            "storage_path": f"supabase-postgres:student.application_checklist_items/{user_id}/{item_id}",
            "file_content": content,
            "uploaded_at": datetime.now(timezone.utc),
        },
        user_id=user_id,
    )


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name or "upload"
