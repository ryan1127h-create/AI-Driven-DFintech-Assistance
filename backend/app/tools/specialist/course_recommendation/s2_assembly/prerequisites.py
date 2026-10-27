"""
S2 — the catalogue's prerequisite and corequisite text as structure the
domain can check: prerequisites as groups that must all be met, each
satisfied by any one of its courses; corequisites as courses of which one
must be taken in the same semester (or already be done).

The graduate-coursework requirement text uses two phrasings, covered here:
  "Must have passed|completed X [or Y ...]"            (prerequisite)
  "Must concurrently take X" / "Must be concurrently enrolled in X [or Y]"
                                                         (corequisite)
A clause in any other wording is kept as `unparsed` text — shown as a
caution, never treated as met or unmet.

Pure functions, no I/O.
"""

from __future__ import annotations

import re

_CODE = re.compile(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b")
_PREREQ = re.compile(r"^must have (?:passed|completed)\s+(.+)$", re.IGNORECASE)
_COREQ = re.compile(r"^must (?:concurrently take|be concurrently enrolled in)\s+(.+)$", re.IGNORECASE)
_CLAUSE_SPLIT = re.compile(r"\s*(?:;|\|)\s*|\s+and\s+", re.IGNORECASE)


def _codes(text: str) -> list[str]:
    return list(dict.fromkeys(_CODE.findall(text.upper())))


def _clauses(text: str) -> list[str]:
    return [c.strip().rstrip(".") for c in _CLAUSE_SPLIT.split(text or "") if c.strip()]


def parse(prerequisite_text: str, corequisite_text: str) -> dict:
    """{"all_of": [[code, ...], ...], "coreq_any_of": [code, ...],
    "unparsed": str | None}."""
    all_of: list[list[str]] = []
    coreq: list[str] = []
    unparsed: list[str] = []

    for clause in _clauses(prerequisite_text):
        match = _PREREQ.match(clause)
        codes = _codes(match.group(1)) if match else []
        if codes:
            all_of.append(codes)
        else:
            unparsed.append(clause)

    for clause in _clauses(corequisite_text):
        match = _COREQ.match(clause)
        codes = _codes(match.group(1)) if match else []
        if codes:
            coreq.extend(c for c in codes if c not in coreq)
        else:
            unparsed.append(clause)

    return {"all_of": all_of, "coreq_any_of": coreq, "unparsed": "; ".join(unparsed) or None}
