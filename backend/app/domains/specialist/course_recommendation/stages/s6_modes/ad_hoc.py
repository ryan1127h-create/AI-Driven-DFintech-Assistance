"""
S6 mode "ad_hoc" — courses matching something specific the student asked
for (a topic, a skill, a Vertical, a style), as one list rather than one
group per requirement. Each course says which open requirement it counts
toward, so the student can see how it fits their degree.

Pure function, no I/O.
"""

from __future__ import annotations

from app.domains.specialist.course_recommendation.models import CandidatePool, Group, ModeInput
from app.domains.specialist.course_recommendation.stages.s6_modes import recommendation

NO_MATCH_NOTE = (
    "No course matched what you asked for specifically, so these are the "
    "best fits for your degree and goals instead."
)


class AdHoc:
    def assemble(self, selected: ModeInput, pool: CandidatePool) -> list[Group]:
        return [{
            "slot_id": "ad_hoc",
            "slot_type": "ad_hoc",
            "label": "Courses matching your request",
            "required_pick_count": 0,
            "recommendations": [
                recommendation.build(
                    pick, pool, recommended=True,
                    counts_toward=pick.slot.label if pick.slot else None,
                )
                for pick in selected.top_picks
            ],
            "note": None if selected.top_matches_request else NO_MATCH_NOTE,
        }]
