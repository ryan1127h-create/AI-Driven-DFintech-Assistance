"""Single source of truth for OpenAI-compatible LLM credentials.

Lookup priority (highest first):
  1. NVIDIA env vars (NVIDIA_API_KEY / NVIDIA_MODEL / NVIDIA_BASE_URL)
  2. DeepSeek env vars (DEEPSEEK_API_KEY / DEEPSEEK_MODEL / DEEPSEEK_BASE_URL)
  3. local file data/.deepseek.json  (written by the /settings page)
  4. built-in defaults

All LLM-calling code reads through here dynamically, so saving a key in the
web UI takes effect immediately without a restart. The key is never logged and
never echoed back in full (see status()).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_SECRET_FILE = Path(__file__).resolve().parents[1] / "data" / ".deepseek.json"
_DEFAULT_MODEL = "deepseek-v4-pro"
_DEFAULT_EMBEDDING_MODEL = "deepseek-embedding"
_DEFAULT_BASE_URL = "https://api.deepseek.com"
_NVIDIA_DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"
_NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

_SMTP_FILE = Path(__file__).resolve().parents[1] / "data" / ".smtp.json"
_DEFAULT_SMTP_PORT = 587


def _read_smtp_file() -> dict:
    if not _SMTP_FILE.exists():
        return {}
    try:
        return json.loads(_SMTP_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _read_file() -> dict:
    if not _SECRET_FILE.exists():
        return {}
    try:
        # utf-8-sig:兼容带 BOM 的 .deepseek.json(Windows/某些编辑器会写 BOM),
        # 否则 json.loads 会因 BOM 解析失败、静默返回空,导致读不到 key。
        return json.loads(_SECRET_FILE.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_nvidia_api_key() -> str | None:
    return (
        os.getenv("NVIDIA_API_KEY")
        or _read_file().get("nvidia_api_key")
        or None
    )


def get_deepseek_api_key() -> str | None:
    return (
        os.getenv("DEEPSEEK_API_KEY")
        or _read_file().get("api_key")
        or None
    )


def get_api_key() -> str | None:
    return get_nvidia_api_key() or get_deepseek_api_key()


def get_model() -> str:
    if get_nvidia_api_key():
        return (
            os.getenv("NVIDIA_MODEL")
            or _read_file().get("nvidia_model")
            or _NVIDIA_DEFAULT_MODEL
        )
    return os.getenv("DEEPSEEK_MODEL") or _read_file().get("model") or _DEFAULT_MODEL


def get_embedding_model() -> str:
    return (
        os.getenv("DEEPSEEK_EMBEDDING_MODEL")
        or _read_file().get("embedding_model")
        or _DEFAULT_EMBEDDING_MODEL
    )


def get_base_url() -> str:
    if get_nvidia_api_key():
        return (
            os.getenv("NVIDIA_BASE_URL")
            or _read_file().get("nvidia_base_url")
            or _NVIDIA_DEFAULT_BASE_URL
        )
    return os.getenv("DEEPSEEK_BASE_URL") or _read_file().get("base_url") or _DEFAULT_BASE_URL


def get_embedding_base_url() -> str:
    """Embedding endpoint, independent of chat. Falls back to the chat base_url.

    Lets chat run on one provider (e.g. DeepSeek) and embeddings on another
    (e.g. an OpenAI-compatible embedding service) — the "swap models on
    delivery" seam. Set via env EMBEDDING_BASE_URL or file `embedding_base_url`.
    """
    return (
        os.getenv("EMBEDDING_BASE_URL")
        or _read_file().get("embedding_base_url")
        or get_base_url()
    )


def get_embedding_api_key() -> str | None:
    """Embedding key, independent of chat.

    A NVIDIA chat key is intentionally not reused for embeddings because the
    hosted DeepSeek chat endpoint is not the embedding endpoint. Configure
    EMBEDDING_API_KEY explicitly when an embedding provider is available.
    """
    explicit = os.getenv("EMBEDDING_API_KEY") or _read_file().get("embedding_api_key")
    if explicit:
        return explicit
    if get_nvidia_api_key():
        return None
    return (
        os.getenv("DEEPSEEK_API_KEY")
        or _read_file().get("api_key")
        or None
    )


def is_configured() -> bool:
    return bool(get_api_key())


def embedding_is_configured() -> bool:
    return bool(get_embedding_api_key())


def set_credentials(api_key: str | None = None, model: str | None = None,
                    base_url: str | None = None,
                    nvidia_api_key: str | None = None,
                    nvidia_model: str | None = None,
                    nvidia_base_url: str | None = None) -> None:
    """Persist credentials to the local secret file (0600 where supported)."""
    data = _read_file()
    if api_key:
        data["api_key"] = api_key.strip()
    if model:
        data["model"] = model.strip()
    if base_url:
        data["base_url"] = base_url.strip()
    if nvidia_api_key:
        data["nvidia_api_key"] = nvidia_api_key.strip()
    if nvidia_model:
        data["nvidia_model"] = nvidia_model.strip()
    if nvidia_base_url:
        data["nvidia_base_url"] = nvidia_base_url.strip()
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SECRET_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(_SECRET_FILE, 0o600)
    except OSError:
        pass  # best effort on Windows


def _mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) >= 4 else "…"


def status() -> dict:
    """Safe-to-display status. Never includes the full key."""
    key = get_api_key()
    source = "none"
    if os.getenv("NVIDIA_API_KEY"):
        source = "nvidia environment"
    elif _read_file().get("nvidia_api_key"):
        source = "nvidia local file"
    elif os.getenv("DEEPSEEK_API_KEY"):
        source = "environment"
    elif _read_file().get("api_key"):
        source = "local file"
    return {
        "configured": bool(key),
        "key_hint": _mask(key) if key else None,
        "model": get_model(),
        "source": source,
    }


def chat_providers() -> list[dict]:
    """Configured chat providers in failover order."""
    providers: list[dict] = []
    nvidia_key = get_nvidia_api_key()
    if nvidia_key:
        providers.append({
            "name": "nvidia",
            "api_key": nvidia_key,
            "base_url": (
                os.getenv("NVIDIA_BASE_URL")
                or _read_file().get("nvidia_base_url")
                or _NVIDIA_DEFAULT_BASE_URL
            ),
            "model": (
                os.getenv("NVIDIA_MODEL")
                or _read_file().get("nvidia_model")
                or _NVIDIA_DEFAULT_MODEL
            ),
            "extra_body": {"chat_template_kwargs": {"thinking": False}},
        })
    deepseek_key = get_deepseek_api_key()
    if deepseek_key:
        providers.append({
            "name": "deepseek",
            "api_key": deepseek_key,
            "base_url": (
                os.getenv("DEEPSEEK_BASE_URL")
                or _read_file().get("base_url")
                or _DEFAULT_BASE_URL
            ),
            "model": (
                os.getenv("DEEPSEEK_MODEL")
                or _read_file().get("model")
                or _DEFAULT_MODEL
            ),
            "extra_body": None,
        })
    return providers


def test_connection() -> tuple[bool, str]:
    """Make a minimal API call to verify the key works. Returns (ok, message)."""
    key = get_api_key()
    if not key:
        return False, "API key is not configured"
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=get_base_url())
        client.models.list()  # cheap auth check
        return True, "Connection succeeded; key is valid"
    except Exception as e:
        return False, f"Connection failed: {e}"


# ---------- SMTP credentials (env > file > default) ----------

def get_smtp_host() -> str | None:
    return os.getenv("SMTP_HOST") or _read_smtp_file().get("smtp_host") or None


def get_smtp_port() -> int:
    val = os.getenv("SMTP_PORT") or _read_smtp_file().get("smtp_port") or _DEFAULT_SMTP_PORT
    try:
        return int(val)
    except (TypeError, ValueError):
        return _DEFAULT_SMTP_PORT


def get_smtp_username() -> str | None:
    return os.getenv("SMTP_USERNAME") or _read_smtp_file().get("smtp_username") or None


def get_smtp_password() -> str | None:
    return os.getenv("SMTP_PASSWORD") or _read_smtp_file().get("smtp_password") or None


def get_smtp_from() -> str | None:
    return (
        os.getenv("SMTP_FROM")
        or _read_smtp_file().get("smtp_from")
        or get_smtp_username()
    )


def get_smtp_use_tls() -> bool:
    env = os.getenv("SMTP_USE_TLS")
    if env is not None:
        return env.strip().lower() not in ("0", "false", "no")
    file_val = _read_smtp_file().get("smtp_use_tls")
    return True if file_val is None else bool(file_val)


def smtp_configured() -> bool:
    return bool(get_smtp_host() and get_smtp_username() and get_smtp_password())
