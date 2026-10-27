"""Exercises dispatch/localization.py's localize() directly: the
English/unset fast path skips the LLM entirely, a non-English language
triggers exactly one conversion call, and every failure mode (LLM error,
empty output, setting off) degrades to the original English answer rather
than raising."""

from __future__ import annotations

from app.core.config import settings
from app.orchestrator.dispatch import localization as localize_tool
from app.orchestrator.dispatch.localization import LocalizeInput
from app.tools.contracts import ToolAnswer


def _input(reply_language: str = "en", message: str = "What's the tuition fee?", text: str = "Tuition is S$74,120.") -> LocalizeInput:
    return LocalizeInput(
        reply_language=reply_language, user_message=message,
        answer=ToolAnswer(text=text, sources=["https://example.com"], agent_used="financial_agent"),
    )


def test_english_skips_the_llm_call_entirely(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "should not be used")
    inp = _input("en")
    result = localize_tool.localize(inp)
    assert result is inp.answer
    assert calls == []


def test_unset_or_empty_language_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    localize_tool.localize(_input(""))
    assert calls == []


def test_non_english_triggers_exactly_one_conversion_call(monkeypatch):
    calls = []

    def _fake_complete(system_prompt, payload, **kwargs):
        calls.append((system_prompt, payload))
        return "学费是 S$74,120。"

    monkeypatch.setattr(localize_tool.llm, "complete", _fake_complete)
    result = localize_tool.localize(_input("zh", "学费是多少？"))
    assert len(calls) == 1
    assert result.text == "学费是 S$74,120。"
    assert result.sources == ["https://example.com"]
    assert result.agent_used == "financial_agent"


def test_llm_error_falls_back_to_the_original_answer(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(localize_tool.llm, "complete", _boom)
    inp = _input("zh")
    result = localize_tool.localize(inp)
    assert result is inp.answer


def test_empty_conversion_output_falls_back_to_the_original(monkeypatch):
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "   ")
    inp = _input("ja")
    result = localize_tool.localize(inp)
    assert result is inp.answer


def test_settings_kill_switch_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    monkeypatch.setattr(settings, "enable_localization", False)
    try:
        inp = _input("zh")
        result = localize_tool.localize(inp)
        assert calls == []
        assert result.text == inp.answer.text
    finally:
        monkeypatch.setattr(settings, "enable_localization", True)


def test_empty_answer_text_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    localize_tool.localize(_input("zh", text=""))
    assert calls == []


# --- only replies not already in the reply language are converted ----------------

def test_a_reply_already_in_the_language_skips_the_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    text = "学费是 **S$76,409**（含消费税），适用于 2027 年 8 月入学。详情见 https://www.comp.nus.edu.sg/ 和 FT5005。"
    inp = _input("zh", "学费是多少？", text)
    assert localize_tool.localize(inp) is inp.answer
    assert calls == []


def test_a_conversion_that_changes_a_figure_is_discarded(monkeypatch):
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "学费是 S$74,210。")
    inp = _input("zh", "学费是多少？")
    assert localize_tool.localize(inp) is inp.answer


def test_a_translated_date_keeps_the_conversion(monkeypatch):
    monkeypatch.setattr(localize_tool.llm, "complete", lambda *a, **k: "截止日期是 2027 年 1 月 31 日，学费 S$76,409。")
    inp = _input("zh", "截止日期？", "The deadline is 31 January 2027 and tuition is S$76,409.")
    assert localize_tool.localize(inp).text.startswith("截止日期是")


# --- reply_language --------------------------------------------------------------

from app.core import reply_language  # noqa: E402


def test_the_instruction_names_the_language():
    assert "write the whole reply in Chinese" in reply_language.instruction("zh")
    assert "Japanese" in reply_language.instruction("ja")
    assert "language of the user's message" in reply_language.instruction(None)


def test_matches_tells_a_reply_in_the_wrong_script_or_in_english():
    english = "The tuition fee for the August 2027 intake is S$76,409 including GST, and you can apply online."
    chinese = "2027 年 8 月入学的学费是 S$76,409（含消费税），可以在 NUS Graduate Admission System 网上申请。"
    assert reply_language.matches(english, "en") and not reply_language.matches(chinese, "en")
    assert reply_language.matches(chinese, "zh") and not reply_language.matches(english, "zh")
    assert reply_language.matches("学費は S$76,409 です。オンラインで申請できます。", "ja")
    assert not reply_language.matches(chinese, "ja")  # Han without kana is not Japanese
    assert not reply_language.matches(english, "fr")
    assert reply_language.matches("Les frais de scolarité sont de S$76,409 pour la promotion d'août 2027.", "fr")
