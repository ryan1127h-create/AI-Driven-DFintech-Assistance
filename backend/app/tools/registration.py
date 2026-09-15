"""
Registers every chatbot-facing, domain-backed Tool into the shared
registry. Imported once, by main.py at startup — nothing else needs to
import this module.

Orchestration-internal stages (intent classification, routing, evaluation,
synthesis, localization) are NOT registered here — they're plain functions
inside app/orchestrator/ now, not Tools (see
app/orchestrator/dispatch/evaluation.py's module docstring for why).
Everything registered below is a genuine chatbot-facing specialist: it has
real trigger_intents and is reachable via intent classification.
"""

from __future__ import annotations

from app.tools.contracts import registry
from app.tools.specialist.assessment_tool import ASSESSMENT_TOOL
from app.tools.specialist.career_planning_tool import CAREER_TOOL
from app.tools.specialist.course_recommendation_tool import COURSE_RECOMMENDATION_TOOL
from app.tools.specialist.knowledge_qa_tool import ACADEMIC_TOOL, ADMISSIONS_TOOL, FAQ_TOOL, FINANCIAL_TOOL
from app.tools.specialist.program_comparison_tool import COMPARISON_TOOL


def register_all() -> None:
    for tool in (
        ADMISSIONS_TOOL, ACADEMIC_TOOL, FINANCIAL_TOOL, FAQ_TOOL,
        CAREER_TOOL, COMPARISON_TOOL, ASSESSMENT_TOOL, COURSE_RECOMMENDATION_TOOL,
    ):
        registry.register(tool)
