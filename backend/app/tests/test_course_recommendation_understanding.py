"""Exercises the tool's s1_understanding/: the structured request a message
is read into (invalid entries dropped, not fatal), the parser's fallback
to "no filters", and that parsing runs alongside S2's data gathering.
The parsing model is always stubbed."""

from __future__ import annotations

import json
import threading

from langchain_core.messages import HumanMessage

from app.tools.specialist.course_recommendation import tool
from app.tools.specialist.course_recommendation.s1_understanding import parser
from app.tools.specialist.course_recommendation.s1_understanding.schema import ParsedRequest
from app.tools.turn_context import TurnState


def _reply(monkeypatch, payload):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: payload if isinstance(payload, str) else json.dumps(payload))


def test_a_message_is_read_into_a_request(monkeypatch):
    _reply(monkeypatch, {
        "include_codes": ["ft5011"], "exclude_codes": ["FT5003"], "preferred_skills": ["ai_ml"],
        "keywords": ["deep learning"], "vertical_preference": ["financial_data_analytics_intelligence"],
        "workload_style": "less_project", "study_mode": "part_time", "capstone_intent": None,
    })
    parsed = parser.parse("…", "ad_hoc")
    assert parsed.mode == "ad_hoc" and not parsed.parse_failed
    assert parsed.include_codes == ["FT5011"] and parsed.exclude_codes == ["FT5003"]
    assert parsed.preferred_skills == ["ai_ml"] and parsed.keywords == ["deep learning"]
    assert parsed.vertical_preference == ["financial_data_analytics_intelligence"]
    assert (parsed.workload_style, parsed.study_mode) == ("less_project", "part_time")


def test_entries_outside_the_vocabularies_are_dropped_not_fatal(monkeypatch):
    _reply(monkeypatch, {
        "include_codes": ["FT5011", "Deep Learning"], "preferred_skills": ["ai_ml", "cooking"],
        "vertical_preference": ["Vertical #9"], "workload_style": "weekends", "study_mode": "sometimes",
        "keywords": ["  trading  ", "", 42],
    })
    parsed = parser.parse("…", None)
    assert parsed.mode == "degree_overview"
    assert parsed.include_codes == ["FT5011"] and parsed.preferred_skills == ["ai_ml"]
    assert parsed.vertical_preference == [] and parsed.workload_style is None and parsed.study_mode is None
    assert parsed.keywords == ["trading"]


def test_unparseable_output_means_no_filters(monkeypatch):
    _reply(monkeypatch, "Sure! Here are the filters: ...")
    parsed = parser.parse("…", "ad_hoc")
    assert parsed.parse_failed and parsed.mode == "ad_hoc" and parsed.keywords == []


def test_a_model_error_means_no_filters(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(parser.llm, "complete", broken)
    assert parser.parse("…", None).parse_failed


def test_an_empty_message_needs_no_model_call(monkeypatch):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert parser.parse("   ", "ad_hoc") == ParsedRequest(mode="ad_hoc")


def test_parsing_runs_alongside_data_gathering(monkeypatch):
    # Each side waits for the other to start: run one after the other, this
    # would time out instead of returning.
    parse_started, gather_started = threading.Event(), threading.Event()

    def _parse(message, mode):
        parse_started.set()
        assert gather_started.wait(5)
        return ParsedRequest(mode="ad_hoc")

    def _prefetch(user_id, hint):
        gather_started.set()
        assert parse_started.wait(5)
        return "prefetched"

    monkeypatch.setattr(tool.parser, "parse", _parse)
    monkeypatch.setattr(tool, "prefetch", _prefetch)
    state = TurnState(messages=[HumanMessage("python courses")], user_id="u1", course_mode_hint="ad_hoc")
    parsed, prefetched = tool._understand_and_gather(state, "python courses")
    assert parsed.mode == "ad_hoc" and prefetched == "prefetched"
