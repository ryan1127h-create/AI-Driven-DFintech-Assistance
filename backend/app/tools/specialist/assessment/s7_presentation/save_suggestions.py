"""
S7 — the facts the message stated that the profile doesn't hold yet (or
holds differently), offered under the reply for saving (see ToolAnswer
.save_suggestions). Only what the message itself said is offered, and only
when the whole profile was read: a list field is offered as the stored
list plus the new items, and a test as the stored tests with that one
added or replaced — built on a profile that couldn't be read, either would
replace what is stored.

Pure function: it compares what S1 parsed with what S2 prefetched.
"""

from __future__ import annotations

from app.tools.specialist.assessment.s1_understanding.schema import MULTI_CHOICES, StatedFacts
from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched


def _key(item):
    return item.get("key") if isinstance(item, dict) else item


def _tests(stored: list, stated: list) -> list | None:
    """The stored tests with the stated ones added or replaced; None when
    nothing changes."""
    by_key = {t["key"]: t for t in stored if isinstance(t, dict) and t.get("key")}
    changed = False
    for test in stated:
        entry = {"key": test["key"], "score": test["score"]}
        if test.get("test_date"):
            entry["test_date"] = test["test_date"]
        current = by_key.get(test["key"])
        if current is None or current.get("score") != entry["score"] \
                or (entry.get("test_date") and current.get("test_date") != entry["test_date"]):
            by_key[test["key"]] = entry
            changed = True
    return list(by_key.values()) if changed else None


def save_suggestions(stated: StatedFacts, prefetched: Prefetched) -> list[dict]:
    if not prefetched.profile_read or not stated.values:
        return []
    stored = prefetched.facts
    suggestions = []
    for key, value in stated.values.items():
        current = stored.get(key)
        if key == "admission_tests":
            merged = _tests(current or [], value)
            if merged is not None:
                suggestions.append({"field_key": key, "value": merged})
        elif key in MULTI_CHOICES:
            items = list(current or [])
            have = {_key(i) for i in items}
            dict_items = any(isinstance(i, dict) for i in items)
            new = [v for v in value if v not in have]
            if new:
                suggestions.append({"field_key": key,
                                    "value": items + [{"key": v} if dict_items else v for v in new]})
        elif value != current:
            suggestions.append({"field_key": key, "value": value})
    return suggestions
