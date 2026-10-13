"""Specialist agents take every input from their tool: programme comparison
builds its facts from given chunks and scores given applicant facts;
knowledge QA and the assessment answer from given context. And the tools assemble those
inputs — LLM calls and data reads are stubbed; no database, no LLM."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.domains.specialist.knowledge_qa import service as qa
from app.domains.specialist.program_comparison import facts, match_scorer
from app.domains.specialist.program_comparison.models import ProgramFacts
from app.tools.knowledge_context import RetrievedContext
from app.tools.specialist import program_comparison_tool
from app.tools.turn_context import TurnState

# --- program comparison -------------------------------------------------------

CHUNKS = [
    {"chunk_key": "competitor:NTU MSc FinTech", "source_table": "competitor_programs",
     "content": "Fees: S$50,000 Format: full-time or part-time Duration: 1 year GMAT/GRE: not required",
     "context": "", "conflict_group": None, "authoritative": False, "metadata": {"source_url": "https://ntu.example"}},
    {"chunk_key": "rule:cur_degree_structure", "source_table": "course_rules", "content": "52 units in total.",
     "context": "", "conflict_group": None, "authoritative": True, "metadata": {}},
    {"chunk_key": "page_06#0", "source_table": "programme_pages", "content": "Tuition is S$60,000.",
     "context": "Fees", "conflict_group": None, "authoritative": True,
     "metadata": {"page_id": "page_06", "source_url": "https://nus.example/fees"}},
]


def test_facts_are_built_from_the_given_chunks():
    competitors = facts.build_competitors(CHUNKS)
    assert [c.name for c in competitors] == ["NTU MSc FinTech"]
    assert "S$50,000" in competitors[0].dimension_text["fees"]
    nus = facts.build_nus(CHUNKS)
    assert "52 units" in nus.dimension_text["curriculum"]
    assert "S$60,000" in nus.dimension_text["fees"]
    assert nus.source_urls == ("https://nus.example/fees",)


def _program(admission=""):
    return ProgramFacts(name="P", is_nus=False, dimension_text={"admission": admission, "curriculum": "part-time"},
                        source_urls=())


@pytest.mark.parametrize("applicant, included, score", [
    ({"has_gmat_gre": True}, True, 100),
    ({"has_gmat_gre": False}, True, 80),     # programme says "not required"
    ({"has_gmat_gre": None}, False, 0),      # unknown: excluded, never guessed
    (None, False, 0),
])
def test_test_score_component_uses_the_given_applicant_facts(applicant, included, score):
    [match] = match_scorer.score_programs([_program("GMAT not required")], [], applicant)
    sub = next(s for s in match.subscores if s.name == "test_scores")
    assert (sub.included, sub.score) == (included, score)


def test_comparison_tool_reads_adm_facts(monkeypatch):
    monkeypatch.setattr(program_comparison_tool, "get_profile_for_purpose",
                        lambda uid, purpose: {"admission_tests": [{"key": "IELTS", "score": 7}]})
    assert program_comparison_tool._applicant_facts("u1") == {"has_gmat_gre": False, "work_years": None}
    monkeypatch.setattr(program_comparison_tool, "get_profile_for_purpose",
                        lambda uid, purpose: {"total_work_years": "3-5"})
    assert program_comparison_tool._applicant_facts("u1")["work_years"] == 3
    monkeypatch.setattr(program_comparison_tool, "get_profile_for_purpose",
                        lambda uid, purpose: {"admission_tests": [{"key": "GRE", "score": 320}]})
    assert program_comparison_tool._applicant_facts("u1")["has_gmat_gre"] is True
    monkeypatch.setattr(program_comparison_tool, "get_profile_for_purpose", lambda uid, purpose: {})
    assert program_comparison_tool._applicant_facts("u1")["has_gmat_gre"] is None


# --- knowledge QA / assessment ----------------------------------------------------

def test_qa_answers_from_the_given_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(qa.qa_agent, "answer",
                        lambda role_prompt, msg, history, *, context, on_event=None, depth=None: seen.update(
                            role_prompt=role_prompt, context=context) or "answer")
    assert qa.retrieval_scope("admissions") == {"admissions"}
    assert qa.answer_topic("admissions", "q?", [], context="CTX", official_sources="- https://nus") == "answer"
    assert seen["context"] == "CTX"
    assert "- https://nus" in seen["role_prompt"] and "{official_sources}" not in seen["role_prompt"]


def test_comparison_fallback_retrieves_for_the_answer(monkeypatch):
    monkeypatch.setattr(program_comparison_tool, "retrieve_context",
                        lambda q, **kw: RetrievedContext(text="CTX", sources=["s1"]))
    monkeypatch.setattr(program_comparison_tool, "answer_with_role_prompt",
                        lambda prompt, msg, history, *, context, on_event=None, depth=None: f"ans:{context}")
    answer = program_comparison_tool._fallback(TurnState(messages=[HumanMessage("NUS vs NTU?")], user_id="u1"))
    assert (answer.text, answer.sources) == ("ans:CTX", ["s1"])
