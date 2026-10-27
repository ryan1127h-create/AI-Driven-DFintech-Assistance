"""
S2 — the data prefetch.py gathers for one turn, handed to builder.py.
Kept in its own module so the builder can depend on this shape without
depending, even indirectly, on the catalogue or profile interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prefetched:
    # The verified programme catalogue (program_catalog.list_programs()).
    programs: list[dict]
    # Profile facts for the "adm" purpose ({} without consent or when the
    # profile couldn't be read).
    facts: dict
    # The applicant's role goal from the "career" purpose: main_target_role
    # and target_role_families.
    role_facts: dict
    # [{tag, name, name_zh, required_skills}] — the role families.
    role_catalog: list[dict]
    # Limitations met while gathering, passed on to the reply's notes.
    notes: tuple[str, ...] = field(default_factory=tuple)
    # The admissions profile was read with consent: `facts` is the whole
    # of it, so a value missing there is missing in the profile too.
    profile_read: bool = False

    @property
    def target_id(self) -> str:
        return next(p["program_id"] for p in self.programs if p["is_target"])

    @property
    def profile_role(self) -> str | None:
        """The profile's main role (else its first listed one), as a known tag."""
        known = {r["tag"] for r in self.role_catalog}
        roles = [self.role_facts.get("main_target_role"), *(self.role_facts.get("target_role_families") or [])]
        return next((r for r in roles if r in known), None)
