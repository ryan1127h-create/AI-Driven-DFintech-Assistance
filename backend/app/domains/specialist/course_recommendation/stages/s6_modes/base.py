"""
The contract every S6 output mode implements. A mode receives what S5
selected (models.ModeInput: each open requirement slot with its picks,
and the top picks across all slots) and decides the shape of the result
(grouped by requirement, one matching list, a semester plan, ...).

To add a mode: implement ModeStrategy in a new module next to this one and
register it in workflow.py's MODES. No stage needs to change.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.specialist.course_recommendation.models import CandidatePool, Group, ModeInput


class ModeStrategy(Protocol):
    def assemble(self, selected: ModeInput, pool: CandidatePool) -> list[Group]:
        ...
