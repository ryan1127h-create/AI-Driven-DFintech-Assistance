"""
S6 exploration — which roles fit the student best: the top
policy.tuning.EXPLORATION_TOP_N of S4's ranking, plus any role the
student lists in their profile that didn't make it (so they see where it
stands). No roadmap: that follows once a role is chosen.
"""

from __future__ import annotations

from app.domains.specialist.career_planning.models import ModeInput, ModeOutput
from app.domains.specialist.career_planning.policy import tuning
from app.domains.specialist.career_planning.stages.s6_modes.base import skills_for

_LOW_CONFIDENCE_NOTE = (
    "Some of these fits rest on skills your profile says nothing about yet, so they may change as you add "
    "your experience and skill levels."
)


class Exploration:
    ranks_all_roles = True
    needs_roadmap = False

    def assemble(self, selected: ModeInput) -> ModeOutput:
        top = selected.fits[: tuning.EXPLORATION_TOP_N]
        listed = tuple(f for f in selected.fits[tuning.EXPLORATION_TOP_N:] if f.preferred)
        roles = top + listed
        notes = (_LOW_CONFIDENCE_NOTE,) if any(f.low_confidence for f in roles) else ()
        return ModeOutput(roles=roles, skills=skills_for(roles, selected.assessments), notes=notes)
