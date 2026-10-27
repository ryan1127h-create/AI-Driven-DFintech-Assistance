"""
Career planning tool — the orchestrator adapter for the career_planning
specialist domain. The packages follow the workflow's tool-side stages:

    gate.py           what to ask the student for first (or alongside)
    s1_understanding/ read the message: the roles it names, facts it states
    s2_assembly/      gather profile and knowledge-base data, build the report
    s7_presentation/  render the domain result into the chat reply

tool.py only sequences them around the domain call.
"""

from app.tools.specialist.career_planning.tool import CAREER_TOOL

__all__ = ["CAREER_TOOL"]
