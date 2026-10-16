"""
S7 — profile facts the user stated this turn that their profile doesn't
hold yet, offered under the reply for saving (see ToolAnswer
.save_suggestions): the programmes they compare MSc DFT with
(competing_programs, as program ids). Only what the message itself said
is offered — a start year alone isn't, since the profile's intake term
also needs the semester.

Pure function: it compares what S1 parsed with what S2 prefetched.
"""

from __future__ import annotations

from app.tools.specialist.program_comparison.s1_understanding.schema import ParsedComparisonRequest
from app.tools.specialist.program_comparison.s2_assembly import programs as program_names
from app.tools.specialist.program_comparison.s2_assembly.prefetched import Prefetched


def save_suggestions(parsed: ParsedComparisonRequest, prefetched: Prefetched, mode: str) -> list[dict]:
    # Without the whole profile the stored list is unknown, and a
    # suggestion built on it would overwrite it.
    if mode != "compare" or not prefetched.profile_read:
        return []
    named = [p for p in parsed.programs if p != prefetched.target_id]
    stored = [n for n in prefetched.facts.get("competing_programs") or [] if isinstance(n, str)]
    known, _ = program_names.resolve(stored, prefetched.programs)
    new = [p for p in named if p not in known]
    return [{"field_key": "competing_programs", "value": [*stored, *new]}] if new else []
