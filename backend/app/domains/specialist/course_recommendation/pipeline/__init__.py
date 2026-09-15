"""
The concrete processing layers of the course_recommendation workflow —
STAGE 2 through STAGE 5 of the design confirmed in the workflow diagrams.
Every module here is a pure function set: no I/O, no database, no LLM
client construction (selection.py calls the shared llm adapter, but never
reaches into a profile store or knowledge base — see the package-level
.importlinter "report-only" contract, which still applies to everything
under this sub-package).
"""

from __future__ import annotations
