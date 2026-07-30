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


# ---------- lifecycle_stage whitelist (all six authority values) ----------
# Spelled out as literals rather than derived from LifecycleStage: the whitelist
# is built from that enum, so iterating the enum here would be a tautology. These
# six strings are the contract, and a change to either side must fail this test.
AUTHORITY_STAGES = ["prospect", "applicant", "admitted", "current", "graduating", "alumni"]


@pytest.mark.parametrize("stage", AUTHORITY_STAGES)
def test_every_authority_stage_survives_coercion(stage):
    # It used to keep only {applicant, current}, so a prospect / admitted /
    # graduating / alumni CV lost its stage silently and came back "missing".
    assert ep.coerce_fields({"lifecycle_stage": stage})["lifecycle_stage"] == stage


@pytest.mark.parametrize("alias", ["enrolled", "student", "alumnus", ""])
def test_a_stage_word_outside_the_authority_vocabulary_is_still_dropped(alias):
    # Widening the whitelist must not turn it into an alias table: `enrolled` and
    # `student` are other systems' words and are translated by
    # common/profile_adapter.py, not accepted here.
    assert "lifecycle_stage" not in ep.coerce_fields({"lifecycle_stage": alias})


# ---------- LLM prompt vocabularies ----------
# The prompt and the whitelist must advertise the same values, or the model is
# asked for words the coercion step then throws away. lifecycle_stage is
# interpolated from the enum, so only its rendered result is checked; the other
# five vocabularies are hand-typed in the prompt and each value is asserted.
PROMPT_VOCABULARIES = [
    "degree_level",
    "field_of_study",
    "technical_proficiency",
    "target_roles",
    "application_type",
]


def test_the_prompt_offers_exactly_the_six_authority_stages():
    # The rendered enumeration, spelled out. Asserting each stage word appears
    # *somewhere* in the prompt was a green tautology: the explanatory sentence
    # further down also names all six, so the list itself could shrink back to
    # (applicant|current) with every such assertion still passing. Verified by
    # mutation.
    assert (
        "lifecycle_stage (prospect|applicant|admitted|current|graduating|alumni)"
        in ep._SYSTEM
    )


@pytest.mark.parametrize("field", PROMPT_VOCABULARIES)
def test_the_prompt_names_every_allowed_value_of_each_hand_typed_vocabulary(field):
    allowed = ep._ALLOWED.get(field) or ep._ALLOWED_LIST[field]
    missing = sorted(v for v in allowed if v not in ep._SYSTEM)
    assert not missing, f"{field}: prompt never names {missing}"


def test_the_prompt_still_asks_for_four_technical_proficiency_levels():
    # Decision 2: the authority keeps 4 levels. If this ever drops to the
    # rag-data pipeline's 3-level scale, `strong` would reach coerce_fields and
    # be dropped, losing the user's stated skill level.
    assert ep._ALLOWED["technical_proficiency"] == {
        "none",
        "basic",
        "intermediate",
        "advanced",
    }
    assert "strong" not in ep._SYSTEM


# ---------- web routes (LLM monkeypatched) ----------
@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_landing_renders(client):
    body = client.get("/").get_data(as_text=True)
    assert "Select your profile type" in body and "Upload CV" in body


def test_extract_text_prefills_form(client, monkeypatch):
    monkeypatch.setattr(
        "student.webapp.extract_fields",
        lambda text: {"degree_level": "bachelor", "field_of_study": "computer_science",
                      "target_roles": ["fintech_pm"], "country": "IN", "work_years": 2},
    )
    resp = client.post("/extract", data={"text": "I'm a CS grad, 2y banking, want fintech PM"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Applicant profile confirmation" in body  # review form shown
    # prefilled selections present
    assert 'value="bachelor" selected' in body
    assert 'value="fintech_pm" checked' in body
    assert 'value="IN"' in body


def test_extract_empty_input_opens_manual_form(client):
    resp = client.post("/extract", data={"text": ""})
    body = resp.get_data(as_text=True)
    assert "Applicant profile confirmation" in body


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
    assert "Applicant profile confirmation" in resp.get_data(as_text=True)
