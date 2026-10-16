"""
Resolves programme names written as plain text — the classifier's
program_hints, the profile's competing_programs — onto catalogue ids,
without a model call. A name matches a programme when, normalised, it
equals one of the programme's names or aliases, or its university's when
that university has a single programme in the catalogue (a university
with several stays ambiguous and is left unmatched). S1's parser handles
the free wording in the message itself; this is the fallback and the
reader for stored names.
"""

from __future__ import annotations

import re
from collections import Counter


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def resolve(names: list[str], programs: list[dict]) -> tuple[list[str], list[str]]:
    """(program ids in the order named, names that matched nothing)."""
    per_university = Counter(p["university"]["university_id"] for p in programs)
    index: dict[str, str] = {}
    for p in programs:
        for name in (p["program_id"], p["name"], p["short_name"], *p.get("aliases", [])):
            index.setdefault(_norm(name), p["program_id"])
    for p in programs:
        u = p["university"]
        if per_university[u["university_id"]] == 1:
            for name in (u["university_id"], u["name"], u["short_name"], *u.get("aliases", [])):
                index.setdefault(_norm(name), p["program_id"])

    ids, unmatched = [], []
    for name in names:
        pid = index.get(_norm(name))
        if pid is None:
            unmatched.append(name)
        elif pid not in ids:
            ids.append(pid)
    return ids, unmatched
