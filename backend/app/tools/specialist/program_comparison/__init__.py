"""
The programme comparison Tool and its workflow steps that live in the
tools layer: S1 reads the message (s1_understanding/), S2 gathers the
turn's data and builds the domain's report (s2_assembly/), S7 renders and
checks the reply (s7_presentation/); gate.py says what the turn could ask
the user for, tool.py sequences them.
"""

from app.tools.specialist.program_comparison.tool import COMPARISON_TOOL

__all__ = ["COMPARISON_TOOL"]
