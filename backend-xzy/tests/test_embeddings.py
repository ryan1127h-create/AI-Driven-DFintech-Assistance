"""Tests for embedding config + client wrapper (offline-safe)."""
from __future__ import annotations

from common import config, embeddings


def test_default_embedding_model():
    assert isinstance(config.get_embedding_model(), str)
    assert config.get_embedding_model()  # non-empty


def test_env_overrides_embedding_model(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_EMBEDDING_MODEL", "school-embed-v1")
    assert config.get_embedding_model() == "school-embed-v1"


def test_embedding_available_false_without_key(monkeypatch):
    monkeypatch.setattr(config, "get_embedding_api_key", lambda: None)
    assert embeddings.embedding_available() is False


def test_embedding_base_url_falls_back_to_chat(monkeypatch):
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.setattr(config, "_read_file", lambda: {})
    monkeypatch.setattr(config, "get_base_url", lambda: "https://chat.example/v1")
    assert config.get_embedding_base_url() == "https://chat.example/v1"


def test_embedding_base_url_env_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example/v1")
    assert config.get_embedding_base_url() == "https://embed.example/v1"


def test_embedding_api_key_independent_of_chat(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-embed-xyz")
    assert config.get_embedding_api_key() == "sk-embed-xyz"


def test_embedding_api_key_falls_back_to_chat(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr(config, "_read_file", lambda: {})
    monkeypatch.setattr(config, "get_api_key", lambda: "sk-chat-fallback")
    assert config.get_embedding_api_key() == "sk-chat-fallback"
