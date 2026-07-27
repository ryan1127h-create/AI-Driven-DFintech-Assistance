"""Global test isolation.

Guarantees the suite never reads or writes the real LLM credentials:
- point common.config._SECRET_FILE at a throwaway temp file
- clear DEEPSEEK_* / NVIDIA_* env vars

This keeps every test offline and deterministic (agents fall back to templates),
and prevents accidental live API calls / quota use / key persistence.
"""
import pytest

from common import config


@pytest.fixture(autouse=True)
def _isolate_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.setattr(config, "_SECRET_FILE", tmp_path / "isolated.deepseek.json")
    for _k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
               "SMTP_FROM", "SMTP_USE_TLS"):
        monkeypatch.delenv(_k, raising=False)
    monkeypatch.setattr(config, "_SMTP_FILE", tmp_path / "isolated.smtp.json")
    yield
