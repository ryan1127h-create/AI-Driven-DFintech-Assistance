"""
Checklist service — static checklist item definitions (see
_CONTRACT_ITEMS below) plus per-user persisted state and file uploads to
object storage. Uploaded files are stored and served back byte-for-byte,
but their content is never inspected or validated beyond type/size —
marking an item "completed" is on the honor system.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from psycopg import errors

from app.adapters.supabase_storage_adapter import storage
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.domains.checklist import repository
from app.domains.checklist.schemas import ChecklistResponse

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


def get_checklist(user_id: str) -> ChecklistResponse:
    states: dict[str, dict] = {}
    implementation_status = "partial"
    notes = [
        "Checklist state is persisted per user.",
        "Automatic verification of uploaded document content is not connected yet.",
    ]

    try:
        states = repository.list_items(user_id)
    except (errors.UndefinedTable, errors.UndefinedColumn):
        implementation_status = "contract_only"
        notes = [
            "Checklist persistence isn't set up in this environment yet.",
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
        if item["requirement"] == "required" and item["status"] not in {"completed", "not_applicable"}
    )
    return ChecklistResponse(
        user_id=user_id,
        implementation_status=implementation_status,
        items=items,
        outstanding_required_count=outstanding_required_count,
        notes=notes,
    )


def patch_checklist_item(item_id: str, fields: dict, user_id: str) -> ChecklistResponse:
    item_id = item_id.strip()
    if item_id not in _VALID_ITEM_IDS:
        raise ValidationError(f"Unknown checklist item_id: {item_id}")
    if not fields:
        raise ValidationError("No checklist fields provided.")

    repository.upsert_item(user_id, item_id, fields)
    return get_checklist(user_id)


async def upload_checklist_file(item_id: str, file: UploadFile, user_id: str) -> ChecklistResponse:
    item_id = item_id.strip()
    if item_id not in _VALID_ITEM_IDS:
        raise ValidationError(f"Unknown checklist item_id: {item_id}")
    if not file.filename:
        raise ValidationError("Uploaded file must have a filename.")

    safe_name = _safe_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValidationError("Unsupported file type. Supported types: " + ", ".join(sorted(_SUPPORTED_SUFFIXES)))

    content = await file.read()
    size = len(content)
    if size == 0:
        raise ValidationError("Uploaded file is empty.")
    if size > _MAX_UPLOAD_BYTES:
        raise ValidationError("Uploaded file is too large. Maximum size is 10 MB.")

    # The object path doubles as the storage_path column value, and
    # deliberately excludes the original filename: each checklist item
    # holds at most one file, so a re-upload (even under a different
    # filename) must land on the exact same object path — that's what
    # makes storage's upsert=true actually overwrite the previous file
    # instead of leaving it behind as an orphan alongside the new one. The
    # display filename still lives in the file_name column below,
    # independent of this path.
    object_path = f"{user_id}/{item_id}/file"
    storage.upload(settings.checklist_storage_bucket, object_path, content, file.content_type)

    return patch_checklist_item(
        item_id,
        {
            "status": "completed",
            "evidence_source": f"uploaded:{safe_name}",
            "file_name": safe_name,
            "content_type": file.content_type,
            "file_size": size,
            "storage_path": object_path,
            "uploaded_at": datetime.now(timezone.utc),
        },
        user_id=user_id,
    )


async def download_checklist_file(item_id: str, user_id: str) -> tuple[bytes, str, str]:
    """Returns (content, file_name, content_type) for a previously uploaded
    checklist item's file, fetched back from object storage."""
    item_id = item_id.strip()
    if item_id not in _VALID_ITEM_IDS:
        raise ValidationError(f"Unknown checklist item_id: {item_id}")

    states = repository.list_items(user_id)
    state = states.get(item_id) or {}
    storage_path = state.get("storage_path")
    if not storage_path:
        raise NotFoundError(f"No uploaded file found for checklist item: {item_id}")

    content = storage.download(settings.checklist_storage_bucket, storage_path)
    file_name = state.get("file_name") or item_id
    content_type = state.get("content_type") or "application/octet-stream"
    return content, file_name, content_type


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name or "upload"
