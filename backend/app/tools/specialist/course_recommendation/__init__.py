"""
Course recommendation tool — the orchestrator adapter for the
course_recommendation specialist domain. The packages follow the
workflow's tool-side stages:

    s2_assembly/      gather profile and knowledge-base data, build the report
    s7_presentation/  render the domain result into the chat reply and check it

tool.py only sequences them around the domain call.
"""

from app.tools.specialist.course_recommendation.tool import COURSE_RECOMMENDATION_TOOL

__all__ = ["COURSE_RECOMMENDATION_TOOL"]
