"""The contract every S6 output mode implements."""

from __future__ import annotations

from typing import Protocol

from app.domains.specialist.career_planning.models import ModeInput, ModeOutput, RoleFit, SkillAssessment
from app.domains.specialist.career_planning.policy import skill_evidence


class ModeStrategy(Protocol):
    # Whether the workflow should rank every role (S4) / build a roadmap (S5).
    ranks_all_roles: bool
    needs_roadmap: bool

    def assemble(self, selected: ModeInput) -> ModeOutput:
        ...


def skills_for(fits: tuple[RoleFit, ...], assessments: dict[str, SkillAssessment]) -> tuple[SkillAssessment, ...]:
    """The graded skills the given roles need, in vocabulary order."""
    needed = {skill for fit in fits for skill in fit.role.required_skills}
    return tuple(assessments[s] for s in skill_evidence.SKILLS if s in needed)
