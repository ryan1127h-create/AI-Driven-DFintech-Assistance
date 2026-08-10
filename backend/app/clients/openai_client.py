"""
OpenAI client factory, used at retrieval time to embed queries with the same
model the knowledge base chunks were embedded with (see
app/services/rag_service.py).
"""

from __future__ import annotations

from app.core.config import settings

EMBED_MODEL = "text-embedding-3-small"

_client = None


def get_openai_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def embed_text(text: str) -> list[float]:
    response = get_openai_client().embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding
