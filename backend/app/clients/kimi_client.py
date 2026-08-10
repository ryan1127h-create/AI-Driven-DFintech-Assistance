"""
Kimi (Moonshot AI) chat-completion client factory, shared by every
service/agent that needs an LLM call (intent classification, RAG answers,
synthesis, history summarization, profile extraction, assessment).
Centralising this means the model name, base URL, and API key are
configured in exactly one place.

Kimi exposes an OpenAI-compatible Chat Completions API, so this uses
langchain_openai.ChatOpenAI pointed at Moonshot's base_url rather than a
Kimi-specific SDK.

Default model is kimi-k2.7-code-highspeed — measured ~4-5x faster than
kimi-k2.6 on identical prompts (lower reasoning-token overhead per call),
with comparable answer quality/tone. Override via the KIMI_MODEL env var if
needed (see app/core/config.py).

Two quirks of the current Kimi model lineup (kimi-k2.6 / kimi-k3 / ...) that
this wrapper works around:
  - temperature is fixed at 1 — any other value is rejected by the API with
    "invalid temperature: only 1 is allowed for this model". Callers can
    still pass a `temperature` argument (kept for interface compatibility
    with call sites tuned for a previous provider), but it is ignored.
  - these are reasoning models: part of `max_tokens` is spent on an internal
    "reasoning_content" the API returns separately (langchain_openai already
    excludes it from `.content`), so `max_tokens` must leave headroom above
    the desired visible answer length or the response can be truncated to
    empty. Call sites should budget generously.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings

DEFAULT_MODEL = settings.kimi_model

# Kimi only accepts temperature=1 for its current model lineup — see module
# docstring. Kept as a named constant rather than silently hardcoded inline
# so the reason is visible at the call site too.
FIXED_TEMPERATURE = 1


def build_chat_llm(temperature: float = 0.7, max_tokens: int = 1024, model: str = DEFAULT_MODEL) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.kimi_api_key,
        base_url=settings.kimi_base_url,
        temperature=FIXED_TEMPERATURE,
        max_tokens=max_tokens,
    )
