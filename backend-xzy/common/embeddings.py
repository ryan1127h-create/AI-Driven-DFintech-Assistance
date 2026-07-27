"""OpenAI-compatible embedding client (design doc 12 §3.4).

Mirrors common/llm.py: reads credentials via common/config.py, fails safe.
Uses the embedding-specific config (EMBEDDING_BASE_URL / EMBEDDING_API_KEY /
DEEPSEEK_EMBEDDING_MODEL), which falls back to the chat config — so chat and
embeddings can run on different providers. Swap providers via config, no code change.
"""
from __future__ import annotations

from . import config


def embedding_available() -> bool:
    return config.embedding_is_configured()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one vector per input text. Raises on misconfig/API error so the
    retriever factory can fall back to BM25."""
    if not texts:
        return []
    from openai import OpenAI

    client = OpenAI(api_key=config.get_embedding_api_key(),
                    base_url=config.get_embedding_base_url())
    resp = client.embeddings.create(model=config.get_embedding_model(), input=texts)
    return [d.embedding for d in resp.data]
