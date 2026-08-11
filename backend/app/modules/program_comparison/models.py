"""Internal domain models for the program_comparison module — structured
views of the knowledge base's competitor_programs chunks and the NUS-side
programme pages (see repository.py for how they are built)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProgramFacts:
    """One programme's raw facts, grouped by comparison dimension.

    dimension_text keys are the supported dimensions ("curriculum", "fees",
    "admission") — value is the source text for that dimension, verbatim
    from the knowledge base. A missing key means no data for that dimension.
    """
    name: str
    is_nus: bool
    dimension_text: dict[str, str]
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class SubScore:
    """One component of a programme's match score. `included=False` means
    the data needed for this component was missing — it is then left out of
    the total instead of being guessed (evidence says what was missing)."""
    name: str
    weight: float
    score: int  # 0-100 within this component (meaningless if not included)
    included: bool
    evidence: str


@dataclass(frozen=True)
class ProgramMatch:
    """A programme's overall match with the user: weighted average of the
    included sub-scores, or None if no component had enough data."""
    program: str
    total: int | None
    subscores: tuple[SubScore, ...] = field(default_factory=tuple)
