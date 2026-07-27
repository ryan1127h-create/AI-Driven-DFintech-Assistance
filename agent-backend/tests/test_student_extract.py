"""Tests for student NL/file extraction (parsing real; LLM monkeypatched)."""
from pathlib import Path

import pytest

from student import extract_profile as ep
from student import webapp

FIX = Path(__file__).parent / "fixtures"


# ---------- file parsing (real files, no LLM) ----------
def test_parse_docx():
    data = (FIX / "resume_priya.docx").read_bytes()
    text = ep.parse_file("resume_priya.docx", data)
    assert "Computer Science" in text and "banking" in text.lower()


def test_parse_pdf():
    data = (FIX / "resume_chen.pdf").read_bytes()
    text = ep.parse_file("resume_chen.pdf", data)
    assert "Singapore" in text and "part-time" in text.lower()


def test_parse_rejects_bad_extension():
    with pytest.raises(ep.ProfileExtractionError):
        ep.parse_file("notes.txt", b"hello")


def test_parse_rejects_oversize():
    with pytest.raises(ep.ProfileExtractionError):
        ep.parse_file("big.pdf", b"x" * (ep.MAX_BYTES + 1))


# ---------- coercion (pure, no LLM) ----------
def test_coerce_keeps_allowed_drops_invalid():
    raw = {
        "lifecycle_stage": "applicant",
        "degree_level": "bachelor",
        "field_of_study": "astrology",          # invalid -> dropped
        "work_years": "2",                       # string int -> coerced
        "country": "india",                      # not 2 letters -> dropped
        "technical_proficiency": "intermediate",
        "target_roles": ["fintech_pm", "wizard"],  # wizard dropped
        "submitted_documents": ["cv"],
    }
    out = ep.coerce_fields(raw)
    assert out["degree_level"] == "bachelor"
    assert "field_of_study" not in out
    assert out["work_years"] == 2
    assert "country" not in out
    assert out["target_roles"] == ["fintech_pm"]
    assert out["submitted_documents"] == ["cv"]


def test_coerce_uppercases_valid_country():
    assert ep.coerce_fields({"country": "in"})["country"] == "IN"


# ---------- web routes (LLM monkeypatched) ----------
@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_landing_renders(client):
    body = client.get("/").get_data(as_text=True)
    assert "选择你的身份" in body and "上传简历" in body


def test_extract_text_prefills_form(client, monkeypatch):
    monkeypatch.setattr(
        "student.webapp.extract_fields",
        lambda text: {"degree_level": "bachelor", "field_of_study": "computer_science",
                      "target_roles": ["fintech_pm"], "country": "IN", "work_years": 2},
    )
    resp = client.post("/extract", data={"text": "I'm a CS grad, 2y banking, want fintech PM"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "申请者资料确认" in body  # review form shown
    # prefilled selections present
    assert 'value="bachelor" selected' in body
    assert 'value="fintech_pm" checked' in body
    assert 'value="IN"' in body


def test_extract_empty_input_opens_manual_form(client):
    resp = client.post("/extract", data={"text": ""})
    body = resp.get_data(as_text=True)
    assert "申请者资料确认" in body


def test_extract_upload_docx_prefills(client, monkeypatch):
    monkeypatch.setattr(
        "student.webapp.extract_fields",
        lambda text: {"field_of_study": "computer_science"},
    )
    data = (FIX / "resume_priya.docx").read_bytes()
    resp = client.post(
        "/extract",
        data={"cv": (__import__("io").BytesIO(data), "resume_priya.docx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert "申请者资料确认" in resp.get_data(as_text=True)
