"""Balanced auto-publish policy.

auto_publish only when: schema valid AND not first onboarding AND trusted source
AND no anomalies. Otherwise route to human review (or reject on invalid schema).
This keeps human effort proportional to risk/change, not to dataset count.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Decision:
    action: str  # "auto_publish" | "needs_review" | "rejected"
    reasons: list[str]


def decide(*, schema_ok: bool, is_first_load: bool, trusted: bool,
           anomalies: list[str]) -> Decision:
    if not schema_ok:
        return Decision("rejected", ["schema_invalid"])
    if is_first_load:
        return Decision("needs_review", ["first_onboarding"])
    if not trusted:
        return Decision("needs_review", ["untrusted_source"])
    if anomalies:
        return Decision("needs_review", list(anomalies))
    return Decision("auto_publish", [])
