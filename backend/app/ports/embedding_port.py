"""
Contract for "turn text into a vector embedding", using whatever model the
knowledge base's stored embeddings were produced with — a different model
here would put queries and stored vectors in different vector spaces,
making cosine similarity meaningless.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    def embed(self, text: str) -> list[float]:
        ...
