"""
Knowledge-base retrieval for the tools layer. Specialist domains never
read data themselves: a tool retrieves here and hands the specialist the
ready-made reference context (plus the sources it cites).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domains.knowledge_retrieval.interface import build_context, cited_sources, retrieve


@dataclass(frozen=True)
class RetrievedContext:
    # Tagged reference text for the prompt; None when nothing was found
    # (the specialist then uses its own "no information" wording).
    text: str | None
    sources: list[str] = field(default_factory=list)
    hits: list = field(default_factory=list)


def retrieve_context(
    query: str, *, top_k: int = 5,
    filter_topics: set[str] | None = None, boost_topics: set[str] | None = None,
) -> RetrievedContext:
    hits = retrieve(query, top_k=top_k, filter_topics=filter_topics, boost_topics=boost_topics)
    return RetrievedContext(
        text=build_context(hits) if hits else None,
        sources=cited_sources(hits),
        hits=list(hits),
    )
