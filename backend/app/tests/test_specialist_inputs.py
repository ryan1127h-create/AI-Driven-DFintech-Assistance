"""Specialist agents take every input from their tool: knowledge QA answers
from the context it is given — LLM calls are stubbed; no database, no LLM."""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import service as qa


def test_qa_answers_from_the_given_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(qa.qa_agent, "answer",
                        lambda role_prompt, msg, history, *, context, on_event=None, depth=None: seen.update(
                            role_prompt=role_prompt, context=context) or "answer")
    assert qa.retrieval_scope("admissions") == {"admissions"}
    assert qa.answer_topic("admissions", "q?", [], context="CTX", official_sources="- https://nus") == "answer"
    assert seen["context"] == "CTX"
    assert "- https://nus" in seen["role_prompt"] and "{official_sources}" not in seen["role_prompt"]

