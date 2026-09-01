"""
Registers every chatbot-facing Tool into the shared registry. Imported
once, by main.py at startup — nothing else needs to import this module.
"""

from __future__ import annotations

from app.tools.assessment_tool import ASSESSMENT_TOOL
from app.tools.career_planning_tool import CAREER_TOOL
from app.tools.contracts import registry
from app.tools.program_comparison_tool import COMPARISON_TOOL
from app.tools.rag_retrieve import ACADEMIC_TOOL, ADMISSIONS_TOOL, FAQ_TOOL, FINANCIAL_TOOL


def register_all() -> None:
    for tool in (
        ADMISSIONS_TOOL, ACADEMIC_TOOL, FINANCIAL_TOOL, FAQ_TOOL,
        CAREER_TOOL, COMPARISON_TOOL, ASSESSMENT_TOOL,
    ):
        registry.register(tool)
