"""
The contract every S6 output mode implements. A mode receives each open
requirement slot with its S5 picks and decides the shape of the result
(grouped by requirement, a filtered top-N, a semester plan, ...).

To add a mode: implement ModeStrategy in a new module next to this one and
register it in workflow.py's MODES. No stage needs to change.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from app.domains.specialist.course_recommendation.models import CandidatePool, Group, SlotPicks


class ModeStrategy(Protocol):
    def assemble(self, slot_picks: Sequence[SlotPicks], pool: CandidatePool) -> list[Group]:
        ...
