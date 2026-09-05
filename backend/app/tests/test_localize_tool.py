"""Exercises localize_tool.py's handler directly: the English/unset fast
path skips the LLM entirely, a non-English language triggers exactly one
conversion call, and every failure mode (LLM error, empty output, setting
off) degrades to the original English answer rather than raising."""

from __future__ import annotations

from app.core.config import settings
from app.tools import localize_tool
from app.tools.contracts import ToolAnswer
from app.tools.localize_tool import LocalizeInput


def _input(reply_language: str = "en", message: str = "What's the tuition fee?", text: str = "Tuition is S$74,120.") -> LocalizeInput:
    return LocalizeInput(
        reply_language=reply_language, user_message=message,
        answer=ToolAnswer(text=text, sources=["https://example.com"], agent_used="financial_agent"),
    )


def test_english_skips_the_llm_call_entirely(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "should not be used")
    inp = _input("en")
    result = localize_tool._handler(inp)
    assert result is inp.answer
    assert calls == []


def test_unset_or_empty_language_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    localize_tool._handler(_input(""))
    assert calls == []


def test_non_english_triggers_exactly_one_conversion_call(monkeypatch):
    calls = []

    def _fake_complete(system_prompt, payload, **kwargs):
        calls.append((system_prompt, payload))
        return "学费是 S$74,120。"

    monkeypatch.setattr(localize_tool.llm, "complete", _fake_complete)
    result = localize_tool._handler(_input("zh", "学费是多少？"))
    assert len(calls) == 1
    assert result.text == "学费是 S$74,120。"
    assert result.sources == ["https://example.com"]
    assert result.agent_used == "financial_agent"


def test_llm_error_falls_back_to_the_original_answer(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(localize_tool.llm, "complete", _boom)
    inp = _input("zh")
    result = localize_tool._handler(inp)
    assert result is inp.answer


def test_empty_conversion_output_falls_back_to_the_original(monkeypatch):
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "   ")
    inp = _input("ja")
    result = localize_tool._handler(inp)
    assert result is inp.answer


def test_settings_kill_switch_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    monkeypatch.setattr(settings, "enable_localization", False)
    try:
        inp = _input("zh")
        result = localize_tool._handler(inp)
        assert calls == []
        assert result.text == inp.answer.text
    finally:
        monkeypatch.setattr(settings, "enable_localization", True)


def test_empty_answer_text_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    localize_tool._handler(_input("zh", text=""))
    assert calls == []
