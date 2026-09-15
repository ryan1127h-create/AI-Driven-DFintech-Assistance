"""
LLM-driven specialist sub-experts — each domain here owns one bounded
business question the orchestrator can dispatch to (career_planning,
program_comparison), or that an external agent calls directly
(course_recommendation), or that's reserved for one not yet implemented
(escalation, application_tracker, alumni_match).

This grouping is physical/organizational only — it introduces no new import
boundary. Each sub-domain still exposes itself to the rest of the app only
through its own interface.py, exactly like every other domain in
app.domains (see app/domains/__init__.py).
"""
