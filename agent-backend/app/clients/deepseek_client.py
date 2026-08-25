"""
DeepSeek chat-completion client factory, shared by every service/agent that
needs an LLM call (intent classification, RAG answers, synthesis, history
summarization, profile extraction, assessment). Centralising this means the
model name, base URL, and API key are configured in exactly one place.

DeepSeek exposes an OpenAI-compatible Chat Completions API, so this uses
langchain_openai.ChatOpenAI pointed at DeepSeek's base_url rather than a
DeepSeek-specific SDK.

Default model is deepseek-chat (DeepSeek-V3, non-reasoning) — every call site
in this codebase wants a direct answer, not a visible chain-of-thought, so
this deliberately avoids deepseek-reasoner (which returns its reasoning as a
separate field and is tuned for different use cases). Override via the
DEEPSEEK_MODEL env var if needed (see app/core/config.py).

Unlike the previous provider this app used (Kimi/Moonshot, which only
accepted temperature=1), DeepSeek's API accepts the full standard 0-2
temperature range, so callers' own temperature is passed straight through:
intent classification asks for 0 (deterministic), free-form chat asks for
0.7 (varied), RAG answers ask for 0.2, etc. — no override needed here.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings

DEFAULT_MODEL = settings.deepseek_model


# Deliberately a factory, not a cached singleton like
# app/clients/openai_client.py's client: call sites each need their own
# temperature/max_tokens/model combination (e.g. temperature=0 for intent
# classification vs. temperature=0.7 for free-form chat), and a
# langchain_openai.ChatOpenAI instance is a cheap, stateless wrapper — there
# is no connection/session worth reusing across calls, unlike the raw SDK
# client openai_client.py caches for its one fixed use (embeddings).
def build_chat_llm(temperature: float = 0.7, max_tokens: int = 1024, model: str = DEFAULT_MODEL) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
