"""
MSc DFT's current key facts — fees, application dates, requirements and
funding for the intake applicants are applying for now — read from the
programme catalogue's checked record and formatted by the knowledge_qa
domain, for every answer that may state programme facts (knowledge Q&A,
and general chat so that it never states them from memory).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.domains.program_catalog import interface as program_catalog
from app.domains.specialist.knowledge_qa import interface as knowledge_qa

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProgrammeFacts:
    # The reference block for a prompt; None when the catalogue can't be read.
    text: str | None
    # The official pages the facts come from, for the reply's sources.
    sources: list[str] = field(default_factory=list)


def current_facts() -> ProgrammeFacts:
    """Never raises: an unreadable catalogue gives no facts, and the answer
    rests on what else it has."""
    try:
        target = next((p for p in program_catalog.list_programs() if p["is_target"]), None)
    except Exception:
        logger.exception("reading the programme catalogue failed")
        return ProgrammeFacts(text=None)
    if target is None:
        return ProgrammeFacts(text=None)
    return ProgrammeFacts(text=knowledge_qa.current_facts(target), sources=knowledge_qa.fact_source_urls(target))
