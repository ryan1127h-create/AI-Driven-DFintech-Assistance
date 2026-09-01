"""
Public interface of the knowledge_retrieval domain — the only module other
domains are allowed to import from app.domains.knowledge_retrieval.

Current consumers:
    - career_planning retrieves career-track reference text
      (filter_topics={"career"}) for its plan narrative.

Usage:
    from app.domains.knowledge_retrieval.interface import retrieve, cited_sources
"""

from __future__ import annotations

from app.domains.knowledge_retrieval.models import Hit
from app.domains.knowledge_retrieval.service import build_context, cited_sources, retrieve

__all__ = ["Hit", "retrieve", "build_context", "cited_sources"]
