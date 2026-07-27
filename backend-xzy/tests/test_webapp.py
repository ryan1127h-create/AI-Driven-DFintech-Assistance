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
    assert "用自然语言修改数据" in body
    assert "status_translations" in body  # target listed


def test_generate_shows_diff(client, monkeypatch):
    # Fake extract: return current file with one field changed (no real DeepSeek).
    target = get_target("status_translations")
    current = json.loads(target.file_path.read_text(encoding="utf-8"))

    def fake_extract(t, cur, instruction):
        d = json.loads(json.dumps(cur))
        d["translations"]["OFFER"]["next_step"] = "请在 7 天内确认"
        return d

    monkeypatch.setattr("admin.extract.extract", fake_extract)
    resp = client.post(
        "/generate",
        data={"target": "status_translations", "admin": "alice",
              "instruction": "改 OFFER 下一步"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "translations.OFFER.next_step" in body  # diff shown
    assert "确认写入" in body  # apply button present


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
    assert "校验失败" in body
    assert "确认写入" not in body  # no write button on invalid draft


def test_generate_extraction_error_shown(client, monkeypatch):
    from admin.extract import ExtractionError

    def boom(t, cur, instruction):
        raise ExtractionError("DEEPSEEK_API_KEY 未设置")

    monkeypatch.setattr("admin.extract.extract", boom)
    resp = client.post(
        "/generate",
        data={"target": "status_translations", "admin": "a", "instruction": "x"},
    )
    body = resp.get_data(as_text=True)
    assert "DEEPSEEK_API_KEY" in body
    assert "确认写入" not in body
