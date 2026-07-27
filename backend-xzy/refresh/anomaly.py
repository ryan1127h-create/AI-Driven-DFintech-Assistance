"""Anomaly detection between the current dataset and a fresh draft.

Anomalies route a refresh to human review. Additions are treated as normal
(not anomalies); removals and value changes on existing records are flagged.
"""
from __future__ import annotations


def detect_catalog_anomalies(current: dict, draft: dict) -> list[str]:
    """Flag suspicious changes in a module_catalog refresh."""
    cur = {m["code"]: m for m in current.get("modules", [])}
    new = {m["code"]: m for m in draft.get("modules", [])}
    out: list[str] = []

    for code in sorted(cur.keys() - new.keys()):
        out.append(f"module_removed: {code}")  # a known module vanished
    for code in sorted(cur.keys() & new.keys()):
        if cur[code].get("name") != new[code].get("name"):
            out.append(f"name_changed: {code}")
        if cur[code].get("credits") != new[code].get("credits"):
            out.append(f"credits_changed: {code}")
    # additions (new.keys() - cur.keys()) are normal -> no anomaly
    return out


def detect_programs_anomalies(current: dict, draft: dict) -> list[str]:
    """Flag suspicious changes in a competitor programs_dataset refresh."""
    cur = {p["program"]: p for p in current.get("programs", [])}
    new = {p["program"]: p for p in draft.get("programs", [])}
    out: list[str] = []
    for name in sorted(cur.keys() - new.keys()):
        out.append(f"program_removed: {name}")
    for name in sorted(cur.keys() & new.keys()):
        cv = cur[name].get("values", {})
        nv = new[name].get("values", {})
        for dim in ("fees", "duration"):
            if cv.get(dim) != nv.get(dim):
                out.append(f"{dim}_changed: {name}")
    return out
