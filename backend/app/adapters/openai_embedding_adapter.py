"""
OpenAI adapter for EmbeddingPort. A cached singleton client (unlike
DeepSeekAdapter's fresh-instance-per-call) since every call site here
embeds one string with the same fixed model — there's no per-call
configuration to vary, so reusing one client avoids reconstructing it on
every retrieval.
"""

from __future__ import annotations

from openai import OpenAI

from app.core.config import settings
from app.ports.embedding_port import EmbeddingPort

EMBED_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingAdapter(EmbeddingPort):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed(self, text: str) -> list[float]:
        response = self._get_client().embeddings.create(model=EMBED_MODEL, input=text)
        return response.data[0].embedding


embedding = OpenAIEmbeddingAdapter(settings.openai_api_key)
