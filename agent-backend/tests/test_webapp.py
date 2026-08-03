"""Smoke tests for the admin web UI (no real LLM; extract is monkeypatched)."""
import json

import pytest

from admin import webapp
from admin.registry import get_target


@pytest.fixture
def client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_index_renders_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Edit data using natural language" in body
    assert "status_translations" in body  # target listed


def test_generate_shows_diff(client, monkeypatch):
    # Fake extract: return current file with one field changed (no real DeepSeek).
    target = get_target("status_translations")
    current = json.loads(target.file_path.read_text(encoding="utf-8"))

    def fake_extract(t, cur, instruction):
        d = json.loads(json.dumps(cur))
        d["translations"]["OFFER"]["next_step"] = "Please confirm within 7 days"
        return d

    monkeypatch.setattr("admin.extract.extract", fake_extract)
    resp = client.post(
        "/generate",
        data={"target": "status_translations", "admin": "alice",
              "instruction": "change the OFFER next step"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "translations.OFFER.next_step" in body  # diff shown
    assert "Confirm and write" in body  # apply button present


def test_generate_validation_failure_hides_apply(client, monkeypatch):
    def bad_extract(t, cur, instruction):
        d = json.loads(json.dumps(cur))
        del d["translations"]["OFFER"]  # invalid: missing status code
        return d

    monkeypatch.setattr("admin.extract.extract", bad_extract)
    resp = client.post(
        "/generate",
        data={"target": "status_translations", "admin": "a", "instruction": "x"},
    )
    body = resp.get_data(as_text=True)
    assert "Draft validation failed" in body
    assert "Confirm and write" not in body  # no write button on invalid draft


def test_generate_extraction_error_shown(client, monkeypatch):
    from admin.extract import ExtractionError

    def boom(t, cur, instruction):
        raise ExtractionError("DEEPSEEK_API_KEY is not set")

    monkeypatch.setattr("admin.extract.extract", boom)
    resp = client.post(
        "/generate",
        data={"target": "status_translations", "admin": "a", "instruction": "x"},
    )
    body = resp.get_data(as_text=True)
    assert "DEEPSEEK_API_KEY" in body
    assert "Confirm and write" not in body
