"""
S2 — the data prefetch.py gathers for one turn, handed to builder.py.
Kept in its own module so the builder can depend on this shape without
depending, even indirectly, on the profile or knowledge-base interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prefetched:
    # Profile facts for the "career" purpose ({} without consent or when
    # the profile couldn't be read).
    facts: dict
    # The lifecycle stage (an ops field, read on its own).
    stage: str | None
    # [{area, level, required}] programme-readiness gaps (derived labels).
    readiness_gaps: list[dict]
    # [{tag, name, name_zh, definition, required_skills}] — the role families.
    role_catalog: list[dict]
    # [{code, title, tags}] — the courses on offer and their role tags.
    course_links: list[dict]
    # Limitations met while gathering, passed on to the reply's notes.
    notes: tuple[str, ...] = field(default_factory=tuple)
    # How the reply shows the profile facts evidence is drawn from:
    # field_key -> {"label": ..., "values": {raw value as str: display text}}.
    evidence_labels: dict = field(default_factory=dict)
    # True only when the whole career profile was read: signed in, consent
    # given (and confirmed) and the read succeeded. `facts` is {} both when
    # the profile is empty and when it couldn't be read; only this tells
    # them apart.
    profile_read: bool = False

    @property
    def profile_roles(self) -> list[str]:
        """The profile's roles, main first, as known role tags."""
        known = {r["tag"] for r in self.role_catalog}
        roles = [self.facts.get("main_target_role"), *(self.facts.get("target_role_families") or [])]
        return [r for r in dict.fromkeys(roles) if r in known]
