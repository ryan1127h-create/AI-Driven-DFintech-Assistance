"""
Thin orchestrator adapters for the specialist domains under
app/domains/specialist/ — one file per domain (or, for knowledge_qa's four
fixed topics, one file producing several Tools). Each adapter's only job is
translating between the orchestrator's own vocabulary (TurnState, OnEvent,
ToolAnswer) and its domain's plain interface.py — no business logic lives
here, that's the domain's job.
"""
