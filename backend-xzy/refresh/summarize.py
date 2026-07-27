"""Turn fetched content into a structured draft.

Clean sources (and the SampleFetcher) return structured dicts -> passthrough.
Raw text (future HTML scrapers) would be summarized via DeepSeek into the
target schema; not enabled in this version.
"""
from __future__ import annotations


def to_draft(source, raw: dict | str) -> dict:
    if isinstance(raw, dict):
        return raw
    raise NotImplementedError(
        "text summarization is not enabled yet; provide a structured fetcher "
        "or add an LLM summarizer for source " + getattr(source, "name", "?")
    )
