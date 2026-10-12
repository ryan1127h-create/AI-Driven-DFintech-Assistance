"""
The contract every S6 output mode implements. A mode receives what S5
selected (models.ModeInput: each open requirement slot with its picks,
the top picks across all slots, or the requirement pools for a semester)
and decides the shape of the result (grouped by requirement, one matching
list, a semester plan, ...), returned as models.ModeOutput.

To add a mode: implement ModeStrategy in a new module next to this one and
register it in workflow.py's MODES. No stage needs to change.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.specialist.course_recommendation.models import CandidatePool, ModeInput, ModeOutput


class ModeStrategy(Protocol):
    def assemble(self, selected: ModeInput, pool: CandidatePool) -> ModeOutput:
        ...
