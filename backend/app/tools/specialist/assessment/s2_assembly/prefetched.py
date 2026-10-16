"""
S2 — the data prefetch.py gathers for one assessment, handed to
builder.py. Kept in its own module so the builder can depend on this shape
without depending, even indirectly, on the profile or catalogue interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Prefetched:
    # The profile facts the assessment reads ({} without consent, signed
    # out, or when the profile couldn't be read).
    facts: dict
    # field key -> the profile's source for it ("QA", "CV", "DB", ...).
    fact_sources: dict
    # MSc DFT's checked catalogue record (see program_catalog.interface);
    # None when the catalogue couldn't be read.
    programme: dict | None
    today: date
    # True only when the whole profile was read: signed in, consent given
    # (and confirmed) and the reads succeeded — `facts` is {} both for an
    # empty profile and an unread one, and only this tells them apart.
    profile_read: bool = False
    # The consent still needed to use the profile, when that's why it wasn't read.
    consent_missing: str | None = None
    # Limitations met while gathering, passed on to the reply's notes.
    notes: tuple[str, ...] = field(default_factory=tuple)
    # A profile value as the profile shows it ("finance_econ_accounting" ->
    # "Finance / economics / accounting"), for the assessed fields.
    value_labels: dict = field(default_factory=dict)
