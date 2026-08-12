"""Unit tests for checklist service logic. No database involved."""

from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import UploadFile

from app.modules.checklist import service


def test_default_checklist_is_partial_with_required_count(monkeypatch):
    monkeypatch.setattr(service.repository, "list_items", lambda user_id: {})

    result = service.get_checklist()

    assert result.implementation_status == "partial"
    assert result.outstanding_required_count == 7
    assert all(item.status == "not_started" for item in result.items)


def test_persisted_state_is_merged(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "list_items",
        lambda user_id: {
            "cv": {
                "status": "completed",
                "evidence_source": "uploaded:cv.pdf",
                "note": "Checked by user",
                "updated_at": None,
            }
        },
    )

    result = service.get_checklist()
    cv = next(item for item in result.items if item.id == "cv")

    assert cv.status == "completed"
    assert cv.evidence_source == "uploaded:cv.pdf"
    assert result.outstanding_required_count == 6


def test_patch_rejects_unknown_item():
    with pytest.raises(ValueError):
        service.patch_checklist_item("not_real", {"status": "completed"})


def test_patch_writes_and_returns_checklist(monkeypatch):
    writes = []

    def fake_upsert(user_id, item_id, fields):
        writes.append((user_id, item_id, fields))

    monkeypatch.setattr(service.repository, "upsert_item", fake_upsert)
    monkeypatch.setattr(service.repository, "list_items", lambda user_id: {})

    result = service.patch_checklist_item("cv", {"status": "completed"})

    assert writes[0][1] == "cv"
    assert writes[0][2] == {"status": "completed"}
    assert result.items


def test_upload_file_saves_to_supabase_payload(monkeypatch):
    writes = []

    def fake_upsert(user_id, item_id, fields):
        writes.append((user_id, item_id, fields))

    monkeypatch.setattr(service.repository, "upsert_item", fake_upsert)
    monkeypatch.setattr(
        service.repository,
        "list_items",
        lambda user_id: {
            "cv": {
                "status": "completed",
                "evidence_source": "uploaded:cv.pdf",
                "note": None,
                "file_name": "cv.pdf",
                "content_type": "application/pdf",
                "file_size": 7,
                "uploaded_at": None,
                "updated_at": None,
            }
        },
    )

    upload = UploadFile(
        filename="cv.pdf",
        file=io.BytesIO(b"pdfdata"),
        headers={"content-type": "application/pdf"},
    )
    result = asyncio.run(service.upload_checklist_file("cv", upload))

    assert writes[0][1] == "cv"
    assert writes[0][2]["status"] == "completed"
    assert writes[0][2]["file_name"] == "cv.pdf"
    assert writes[0][2]["file_size"] == 7
    assert writes[0][2]["file_content"] == b"pdfdata"
    assert writes[0][2]["storage_path"].startswith("supabase-postgres:")
    cv = next(item for item in result.items if item.id == "cv")
    assert cv.status == "completed"
