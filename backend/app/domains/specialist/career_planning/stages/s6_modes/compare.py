"""
S6 compare — two or three roles side by side, in the order asked: each
one's fit, the skills they all need, and those only some of them do.
"""

from __future__ import annotations

from app.domains.specialist.career_planning.models import Comparison, ModeInput, ModeOutput
from app.domains.specialist.career_planning.policy import tuning
from app.domains.specialist.career_planning.stages.s6_modes.base import skills_for


class Compare:
    ranks_all_roles = False
    needs_roadmap = False

    def assemble(self, selected: ModeInput) -> ModeOutput:
        roles = selected.fits[: tuning.COMPARE_MAX_ROLES]
        skill_sets = [set(f.role.required_skills) for f in roles]
        shared = set.intersection(*skill_sets) if skill_sets else set()
        comparison = Comparison(
            shared_skills=tuple(s for s in roles[0].role.required_skills if s in shared) if roles else (),
            distinct_skills={
                f.role.tag: tuple(s for s in f.role.required_skills if s not in shared) for f in roles
            },
        )
        return ModeOutput(roles=roles, skills=skills_for(roles, selected.assessments), comparison=comparison)
