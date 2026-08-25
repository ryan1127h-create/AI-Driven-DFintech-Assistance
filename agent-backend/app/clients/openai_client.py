"""
OpenAI client factory, used at retrieval time to embed queries with the same
model the knowledge base chunks were embedded with (see
app/services/rag_service.py).
"""

from __future__ import annotations

from app.core.config import settings

EMBED_MODEL = "text-embedding-3-small"

# Cached singleton (unlike app/clients/deepseek_client.py's build_chat_llm(),
# which returns a fresh instance per call): every call site here uses the
# client the exact same way (embed one string with EMBED_MODEL), so there's
# no per-call configuration to vary, and reusing one OpenAI SDK client
# avoids reconstructing it on every retrieval.
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
