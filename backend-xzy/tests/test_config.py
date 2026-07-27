"""Tests for credential config and the /settings web routes."""
import importlib

import pytest

from common import config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Fresh config module pointed at a temp secret file, env cleared."""
    from common import config as c
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr(c, "_SECRET_FILE", tmp_path / ".deepseek.json")
    return c


def test_default_model_when_unset(cfg):
    assert cfg.get_api_key() is None
    assert cfg.get_model() == "deepseek-v4-pro"
    assert cfg.is_configured() is False


def test_set_and_read_back(cfg):
    cfg.set_credentials(api_key="sk-abcd1234", model="deepseek-v4-pro")
    assert cfg.get_api_key() == "sk-abcd1234"
    assert cfg.is_configured() is True


def test_env_overrides_file(cfg, monkeypatch):
    cfg.set_credentials(api_key="sk-fromfile")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fromenv")
    assert cfg.get_api_key() == "sk-fromenv"
    assert cfg.status()["source"] == "environment"


def test_status_never_exposes_full_key(cfg):
    cfg.set_credentials(api_key="sk-secret-tail-9968")
    st = cfg.status()
    assert st["configured"] is True
    assert st["key_hint"] == "…9968"
    assert "sk-secret-tail-9968" not in str(st)  # full key not present


def test_set_only_model_keeps_key(cfg):
    cfg.set_credentials(api_key="sk-keep")
    cfg.set_credentials(model="deepseek-v4-flash")
    assert cfg.get_api_key() == "sk-keep"
    assert cfg.get_model() == "deepseek-v4-flash"


def test_nvidia_env_switches_chat_provider(cfg, monkeypatch):
    cfg.set_credentials(api_key="sk-deepseek-file", model="deepseek-v4-pro")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")

    assert cfg.get_api_key() == "nvapi-test"
    assert cfg.get_model() == "deepseek-ai/deepseek-v4-pro"
    assert cfg.get_base_url() == "https://integrate.api.nvidia.com/v1"
    assert cfg.status()["source"] == "nvidia environment"


def test_nvidia_local_file_switches_chat_provider(cfg):
    cfg.set_credentials(api_key="sk-deepseek-file", nvidia_api_key="nvapi-file")

    assert cfg.get_api_key() == "nvapi-file"
    assert cfg.get_model() == "deepseek-ai/deepseek-v4-pro"
    assert cfg.get_base_url() == "https://integrate.api.nvidia.com/v1"
    assert cfg.status()["source"] == "nvidia local file"


def test_nvidia_model_and_base_url_can_be_overridden(cfg, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro-custom")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://example.nvidia.test/v1")

    assert cfg.get_model() == "deepseek-ai/deepseek-v4-pro-custom"
    assert cfg.get_base_url() == "https://example.nvidia.test/v1"


def test_nvidia_chat_key_is_not_reused_for_embeddings(cfg, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")

    assert cfg.get_embedding_api_key() is None
    assert cfg.embedding_is_configured() is False

    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-embed")
    assert cfg.get_embedding_api_key() == "sk-embed"
    assert cfg.embedding_is_configured() is True


def test_chat_providers_orders_nvidia_then_deepseek(cfg):
    cfg.set_credentials(api_key="sk-deepseek-file", nvidia_api_key="nvapi-file")

    providers = cfg.chat_providers()
    assert [p["name"] for p in providers] == ["nvidia", "deepseek"]
    assert providers[0]["model"] == "deepseek-ai/deepseek-v4-pro"
    assert providers[1]["model"] == "deepseek-v4-pro"


# ---------- web routes (both apps share the same logic) ----------
@pytest.mark.parametrize("module", ["admin.webapp", "student.webapp"])
def test_settings_get_renders(module):
    mod = importlib.import_module(module)
    mod.app.config["TESTING"] = True
    client = mod.app.test_client()
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "DeepSeek" in resp.get_data(as_text=True)


@pytest.mark.parametrize("module", ["admin.webapp", "student.webapp"])
def test_settings_post_save(module, tmp_path, monkeypatch):
    from common import config as c
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(c, "_SECRET_FILE", tmp_path / ".deepseek.json")

    mod = importlib.import_module(module)
    mod.app.config["TESTING"] = True
    client = mod.app.test_client()
    resp = client.post("/settings", data={"action": "save", "api_key": "sk-web123", "model": "deepseek-v4-pro"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "已保存" in body
    assert "…b123" in body          # masked hint = last 4 of sk-web123
    assert "sk-web123" not in body  # full key never rendered
    assert c.get_api_key() == "sk-web123"


# ---------- SMTP config ----------
def test_smtp_not_configured_when_empty(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert config.smtp_configured() is False


def test_smtp_configured_from_env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert config.smtp_configured() is True
    assert config.get_smtp_host() == "smtp.example.com"
    assert config.get_smtp_port() == 587
    assert config.get_smtp_from() == "me@example.com"
    assert config.get_smtp_use_tls() is True
