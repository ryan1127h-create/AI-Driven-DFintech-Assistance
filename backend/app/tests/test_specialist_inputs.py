"""Knowledge QA takes every input from its tool, checks the figures it
cites, formats the programme's current facts, and rewrites follow-ups into
standalone search queries — LLM calls are stubbed; no database, no LLM."""

from __future__ import annotations

from app.domains.specialist.knowledge_qa import facts as qa_facts
from app.domains.specialist.knowledge_qa import guardrail
from app.domains.specialist.knowledge_qa import qa_agent
from app.domains.specialist.knowledge_qa import service as qa

DFT = {
    "name": "Master of Science in Digital Financial Technology", "short_name": "MSc DFinTech",
    "official_url": "https://www.comp.nus.edu.sg/programmes/pg/mdft/",
    "intake_year": 2027, "verified_at": "2026-10-14",
    "facts": {"intake_months": [8], "duration_ft_months": 18, "duration_pt_months": 30,
              "max_candidature_months": 36, "total_credits": 52, "credit_unit": "NUS Units",
              "application_fee": 109, "application_fee_currency": "SGD", "gmat_gre_policy": "recommended",
              "toefl_ibt_min": 90, "toefl_ibt_band_min": 4.5, "ielts_min": 6, "work_exp_policy": "not_required"},
    "fees": [{"amount": 76409, "currency": "SGD", "includes_tax": True, "note": "Covers up to 52 Units.",
              "quote": "Tuition Fees (including prevailing GST 9%) S$76,409",
              "source_url": "https://www.comp.nus.edu.sg/programmes/pg/mdft/scholarships/"}],
    "deadlines": [{"round_label": "August intake", "opens_on": "2026-10-01", "closes_on": "2027-01-31",
                   "source_url": "https://www.comp.nus.edu.sg/programmes/pg/mdft/application/"}],
    "funding": [{"name": "Enhanced Tuition Fee Rebate", "kind": "rebate", "amount_kind": "percent_tuition",
                 "percent": 40, "eligible_categories": ["sg_citizen", "sg_pr"], "bond_required": False,
                 "conditions": None}],
}


# --- current facts ------------------------------------------------------------

def test_current_facts_name_the_intake_and_its_figures():
    text = qa_facts.current_facts(DFT)
    assert "August 2027 intake" in text and "14 October 2026" in text
    assert "S$76,409" in text and "S$109" in text
    assert "opens 1 October 2026, closes 31 January 2027" in text
    assert "full-time 1.5 years, part-time 2.5 years, maximum candidature 3 years" in text
    assert "TOEFL iBT 90" in text and "IELTS 6" in text
    assert "40% of tuition" in text and "Singapore Citizens, Singapore PRs" in text
    assert "given automatically" in text


def test_fact_sources_are_the_pages_the_facts_come_from():
    assert qa_facts.source_urls(DFT) == [
        "https://www.comp.nus.edu.sg/programmes/pg/mdft/",
        "https://www.comp.nus.edu.sg/programmes/pg/mdft/scholarships/",
        "https://www.comp.nus.edu.sg/programmes/pg/mdft/application/",
    ]


# --- guardrail ----------------------------------------------------------------

def test_figures_from_the_sources_pass():
    sources = "Tuition Fees S$76,409. Closing date 31 January 2027. TOEFL 90 or 4.5. Rebate 40%."
    reply = "Tuition is **S$76,409**; apply by 31 January 2027. You need TOEFL 90 (4.5) — rebate 40%."
    assert guardrail.check(reply, sources) == []


def test_a_stale_fee_and_date_are_caught():
    sources = "Tuition Fees S$76,409. Closing date 2027-01-31."
    problems = guardrail.check("Tuition is S$74,120; apply by 31 March 2026.", sources)
    assert any("74120" in p for p in problems)
    assert any("31 March" in p for p in problems)


def test_a_one_step_calculation_with_its_working_passes():
    sources = "Tuition Fees S$76,409. Rebate 40% for Singapore Citizens. Application fee S$109."
    assert guardrail.check("40% of S$76,409 is S$30,563.60, leaving about S$45,845.40.", sources) == []
    assert guardrail.check("S$76,409 plus the S$109 application fee is S$76,518.", sources) == []


def test_a_calculated_figure_without_its_working_is_caught():
    sources = "Tuition Fees S$76,409. Rebate 40% for Singapore Citizens."
    assert guardrail.check("You would pay S$45,845.", sources) == ["figures not in the reference material: 45845"]


def test_abbreviated_and_full_month_names_support_each_other():
    assert guardrail.check("Accept by 2 November 2026.", "must be accepted by 2 Nov 2026") == []
    assert guardrail.check("Apply by Jan 31, 2027.", "closes on 31 January 2027") == []
    assert guardrail.check("Accept by 3 Nov. 2026.", "must be accepted by 2 November 2026") == [
        "dates not in the reference material: 3 November"]


def test_a_word_starting_like_a_month_is_not_a_date():
    assert guardrail.check("Pick 3 Decide-level electives.", "") == []


def test_codes_urls_and_small_counts_are_ignored():
    reply = "Take FT5005 in AY2027/28 with 2 referees: https://nusmods.com/courses/FT5005/2026"
    assert guardrail.check(reply, "FT5005") == []


# --- answer flow --------------------------------------------------------------

def _stub_answers(monkeypatch, replies):
    calls = []

    def answer(role_prompt, msg, history, *, context, facts=None, on_event=None, depth=None, language=None):
        calls.append({"role_prompt": role_prompt, "context": context, "facts": facts, "streamed": on_event is not None})
        return replies[len(calls) - 1]
    monkeypatch.setattr(qa.qa_agent, "answer", answer)
    return calls


def test_qa_answers_from_the_given_facts_and_context(monkeypatch):
    calls = _stub_answers(monkeypatch, ["Tuition is S$76,409."])
    assert qa.retrieval_scope("admissions") == {"admissions"}
    reply = qa.answer_topic("financial", "fee?", [], context="CTX", facts="Tuition S$76,409", on_event=lambda e: None)
    assert reply == "Tuition is S$76,409." and len(calls) == 1
    assert calls[0]["context"] == "CTX" and calls[0]["facts"] == "Tuition S$76,409" and calls[0]["streamed"]
    assert "Financial Advisor" in calls[0]["role_prompt"]


def test_no_figure_is_written_into_the_prompts():
    for spec in qa._TOPICS.values():
        assert not any(ch.isdigit() for ch in spec.focus)


def test_a_failed_check_regenerates_silently_with_the_problem(monkeypatch):
    calls = _stub_answers(monkeypatch, ["Tuition is S$74,120.", "Tuition is S$76,409."])
    reply = qa.answer_topic("financial", "fee?", [], context=None, facts="Tuition S$76,409", on_event=lambda e: None)
    assert reply == "Tuition is S$76,409."
    assert not calls[1]["streamed"] and "74120" in calls[1]["role_prompt"]


def test_figures_from_the_users_own_record_pass(monkeypatch):
    calls = _stub_answers(monkeypatch, ["Application DFT2728-0019, submitted 5 September 2026, needs 2 items."])
    history = [{"role": "system", "content": "application_record: DFT2728-0019, submitted 2026-09-05"},
               {"role": "user", "content": "status?"}]
    reply = qa.answer_topic("admissions", "status?", history, context=None, facts="Tuition S$76,409")
    assert reply.startswith("Application DFT2728-0019") and len(calls) == 1


def test_a_mostly_supported_answer_only_loses_the_unconfirmed_sentence(monkeypatch):
    good = ("Tuition is S$76,409 for the whole programme, including GST. It covers up to 52 units, and the "
            "acceptance fee is credited towards it. Rebates are applied automatically to those eligible.")
    _stub_answers(monkeypatch, [f"{good} The monthly internship allowance is S$1,200.",
                                f"{good} Interns earn about S$1,200 a month."])
    reply = qa.answer_topic("financial", "fee?", [], context="52 units", facts="Tuition S$76,409")
    assert reply.startswith(good) and "1,200" not in reply and "left out a detail" in reply


def test_drop_unsupported_keeps_the_rest_of_a_line():
    text, dropped = guardrail.drop_unsupported("Fees are S$76,409. Allowance is S$1,200.\n\n- Apply by 31 January 2027.",
                                               "S$76,409")
    assert text == "Fees are S$76,409." and dropped == 2


def test_two_failed_checks_point_to_the_official_pages(monkeypatch):
    _stub_answers(monkeypatch, ["S$74,120.", "S$74,120 still."])
    reply = qa.answer_topic("financial", "fee?", [], context=None, facts="Tuition S$76,409")
    assert "couldn't confirm" in reply and "pg-enquiry" in reply


# --- search query -------------------------------------------------------------

def test_a_first_english_question_is_searched_as_is(monkeypatch):
    monkeypatch.setattr(qa_agent.llm, "complete", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    history = [{"role": "system", "content": "Profile."}, {"role": "user", "content": "Tuition fee?"}]
    assert qa_agent.search_query("Tuition fee?", history) == "Tuition fee?"


def test_a_follow_up_or_non_english_question_is_rewritten(monkeypatch):
    seen = {}

    def complete(system_prompt, payload, **kwargs):
        seen["payload"] = payload
        return "MSc DFT tuition fee for local students"
    monkeypatch.setattr(qa_agent.llm, "complete", complete)
    history = [{"role": "user", "content": "Tuition fee?"}, {"role": "assistant", "content": "S$76,409."},
               {"role": "user", "content": "那本地学生呢？"}]
    assert qa_agent.search_query("那本地学生呢？", history) == "MSc DFT tuition fee for local students"
    assert "Tuition fee?" in seen["payload"] and "那本地学生呢？" in seen["payload"]


def test_a_failed_rewrite_falls_back_to_the_message(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("llm down")
    monkeypatch.setattr(qa_agent.llm, "complete", broken)
    assert qa_agent.search_query("学费多少？", [{"role": "user", "content": "学费多少？"}]) == "学费多少？"


def test_in_a_shared_turn_the_answer_keeps_to_its_own_part(monkeypatch):
    calls = _stub_answers(monkeypatch, ["Tuition is S$76,409.", "Tuition is S$76,409."])
    qa.answer_topic("financial", "electives for AI, and the fee?", [], context=None, facts="Tuition S$76,409",
                    other_tools=("course_recommendation",))
    assert "personal course recommendations" in calls[0]["role_prompt"]
    assert "Answer only your own part" in calls[0]["role_prompt"]
    qa.answer_topic("financial", "fee?", [], context=None, facts="Tuition S$76,409")
    assert "Shared message" not in calls[1]["role_prompt"]
