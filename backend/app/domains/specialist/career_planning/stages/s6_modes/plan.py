"""S6 plan — one role: its fit, its graded skills, and the dated roadmap."""

from __future__ import annotations

from app.domains.specialist.career_planning.models import ModeInput, ModeOutput
from app.domains.specialist.career_planning.stages.s6_modes.base import skills_for


class Plan:
    ranks_all_roles = False
    needs_roadmap = True

    def assemble(self, selected: ModeInput) -> ModeOutput:
        roles = selected.fits[:1]
        notes = selected.roadmap.notes if selected.roadmap else ()
        return ModeOutput(
            roles=roles,
            skills=skills_for(roles, selected.assessments),
            roadmap=selected.roadmap,
            notes=notes,
        )
