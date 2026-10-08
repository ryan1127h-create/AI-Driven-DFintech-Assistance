"""
S6 mode "degree_overview" — one group per open requirement slot (mandatory
core, core choice, each Vertical, the Capstone path), each listing its
recommendation(s) first and a few browsable alternatives after.

Pure function, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import CandidatePool, Group, ModeInput, SlotPicks
from app.domains.specialist.course_recommendation.stages.s6_modes import recommendation

SECONDARY_VERTICAL_NOTE = (
    "This Vertical isn't currently the primary source for your remaining "
    "elective requirement (see the other Vertical group for that) — these "
    "are optional courses worth exploring if this direction interests you."
)


def _group(entry: SlotPicks, pool: CandidatePool) -> Group:
    slot = entry.slot
    note = entry.note
    if slot.slot_type == "elective" and slot.required_pick_count == 0 and entry.picks:
        note = f"{note} {SECONDARY_VERTICAL_NOTE}" if note else SECONDARY_VERTICAL_NOTE
    return {
        "slot_id": slot.slot_id,
        "slot_type": slot.slot_type,
        "label": slot.label,
        "required_pick_count": slot.required_pick_count,
        "recommendations": [
            recommendation.build(pick, pool, recommended=index < slot.required_pick_count)
            for index, pick in enumerate(entry.picks)
        ],
        "note": note,
    }


class DegreeOverview:
    def assemble(self, selected: ModeInput, pool: CandidatePool) -> list[Group]:
        return [_group(entry, pool) for entry in selected.slot_picks]
