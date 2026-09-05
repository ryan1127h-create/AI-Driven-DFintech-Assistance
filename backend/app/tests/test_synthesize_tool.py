"""Exercises synthesize_tool.py's handler directly: drafts are combined via
one streamed LLM call, sources are deduped in first-seen order across
drafts, and agent_used is the "+"-joined list of contributing agents."""

from __future__ import annotations

from app.tools import synthesize_tool as st
from app.tools.contracts import ToolAnswer
from app.tools.synthesize_tool import SynthesizeInput


def _fake_stream(chunks):
    def _stream(system_prompt, history, **kwargs):
        yield from chunks
    return _stream


def test_synthesize_streams_tokens_through_on_event(monkeypatch):
    monkeypatch.setattr(st.llm, "stream", _fake_stream(["Merged ", "answer."]))
    events = []
    inp = SynthesizeInput(
        user_message="What's the fee and the deadline?",
        partials=[
            ("financial", ToolAnswer(text="Fee is S$74,120.", sources=["https://a.example"], agent_used="financial_agent")),
            ("admissions", ToolAnswer(text="Deadline is March.", sources=["https://b.example"], agent_used="admissions_agent")),
        ],
    )
    result = st._handler(inp, on_event=events.append)
    assert result.text == "Merged answer."
    assert [e["text"] for e in events] == ["Merged ", "answer."]


def test_synthesize_dedupes_sources_in_first_seen_order(monkeypatch):
    monkeypatch.setattr(st.llm, "stream", _fake_stream(["ok"]))
    inp = SynthesizeInput(
        user_message="q",
        partials=[
            ("a", ToolAnswer(text="a", sources=["https://shared.example", "https://a-only.example"], agent_used="a_agent")),
            ("b", ToolAnswer(text="b", sources=["https://shared.example", "https://b-only.example"], agent_used="b_agent")),
        ],
    )
    result = st._handler(inp)
    assert result.sources == ["https://shared.example", "https://a-only.example", "https://b-only.example"]


def test_synthesize_joins_agent_used(monkeypatch):
    monkeypatch.setattr(st.llm, "stream", _fake_stream(["ok"]))
    inp = SynthesizeInput(
        user_message="q",
        partials=[
            ("a", ToolAnswer(text="a", agent_used="financial_agent")),
            ("b", ToolAnswer(text="b", agent_used="admissions_agent")),
        ],
    )
    result = st._handler(inp)
    assert result.agent_used == "financial_agent+admissions_agent"


def test_synthesize_preserves_classification_order_not_dict_order(monkeypatch):
    seen_prompt = {}

    def _stream(system_prompt, history, **kwargs):
        seen_prompt["value"] = system_prompt
        yield "ok"

    monkeypatch.setattr(st.llm, "stream", _stream)
    inp = SynthesizeInput(
        user_message="q",
        partials=[
            ("financial", ToolAnswer(text="FEE_TEXT", agent_used="financial_agent")),
            ("admissions", ToolAnswer(text="ADM_TEXT", agent_used="admissions_agent")),
        ],
    )
    st._handler(inp)
    assert seen_prompt["value"].index("FEE_TEXT") < seen_prompt["value"].index("ADM_TEXT")
