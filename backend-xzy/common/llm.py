"""LLM client wrapper for OpenAI-compatible DeepSeek providers.

The LLM is used ONLY for natural-language explanation / narrative. All
decisions (eligibility, missing items, status, recommendations) are made by
deterministic rule engines, never here.

Offline/degraded mode: when neither NVIDIA_API_KEY nor DEEPSEEK_API_KEY is
configured, `explain` returns the provided fallback text. This keeps every
agent runnable and tests deterministic without network access.
"""
from __future__ import annotations

from . import config


def _get_client(provider: dict):
    # Built fresh per call so a key saved at runtime (via /settings) takes effect.
    from openai import OpenAI

    return OpenAI(api_key=provider["api_key"], base_url=provider["base_url"])


def _providers() -> list[dict]:
    return config.chat_providers()


def available() -> bool:
    """True if an API key is configured (live mode)."""
    return bool(_providers())


def explain(system: str, user: str, fallback: str) -> str:
    """Return a natural-language string from the configured LLM, or fallback.

    Low temperature for stable, grounded phrasing. Any API error falls back to
    the deterministic template so the agent never crashes on LLM issues
    (requirements doc: "agents must fail safely").
    """
    if not available():
        return fallback
    for provider in _providers():
        try:
            kwargs = {
                "model": provider["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 600,
            }
            if provider.get("extra_body"):
                kwargs["extra_body"] = provider["extra_body"]
            resp = _get_client(provider).chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if content:
                return content.strip()
        except Exception:
            continue
    return fallback


def explain_map(system: str, user: str, fallback: dict[str, str]) -> dict[str, str]:
    """One LLM call returning a JSON object {key: text}.

    Used to batch many small explanations into a single request. Offline or on
    any error/parse failure, returns `fallback` unchanged (deterministic).
    The returned map is filtered to the keys present in `fallback`, and any
    missing key falls back to its template value.
    """
    if not available():
        return fallback
    import json

    for provider in _providers():
        try:
            kwargs = {
                "model": provider["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
                "response_format": {"type": "json_object"},
            }
            if provider.get("extra_body"):
                kwargs["extra_body"] = provider["extra_body"]
            resp = _get_client(provider).chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            data = json.loads(content) if content else {}
        except Exception:
            continue
        if isinstance(data, dict):
            return {k: (data.get(k) or fallback[k]) for k in fallback}
    return fallback
