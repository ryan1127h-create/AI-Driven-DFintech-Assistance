"""
Registers every chatbot-facing Tool into the shared registry. Imported
once, by main.py at startup — nothing else needs to import this module.
"""

from __future__ import annotations

from app.tools.assessment_tool import ASSESSMENT_TOOL
from app.tools.career_planning_tool import CAREER_TOOL
from app.tools.contracts import registry
from app.tools.evaluate_branch_tool import EVALUATE_BRANCH_TOOL
from app.tools.localize_tool import LOCALIZE_TOOL
from app.tools.program_comparison_tool import COMPARISON_TOOL
from app.tools.rag_retrieve import ACADEMIC_TOOL, ADMISSIONS_TOOL, FAQ_TOOL, FINANCIAL_TOOL
from app.tools.synthesize_tool import SYNTHESIZE_TOOL


def register_all() -> None:
    for tool in (
        ADMISSIONS_TOOL, ACADEMIC_TOOL, FINANCIAL_TOOL, FAQ_TOOL,
        CAREER_TOOL, COMPARISON_TOOL, ASSESSMENT_TOOL,
        # No trigger_intents — called directly by name from dispatch.py,
        # never routed to by intent classification (see each Tool's own
        # module docstring for why they're still registered like everything
        # else rather than special-cased).
        EVALUATE_BRANCH_TOOL, SYNTHESIZE_TOOL, LOCALIZE_TOOL,
    ):
        registry.register(tool)
