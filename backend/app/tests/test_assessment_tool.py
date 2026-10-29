"""The assessment tool layer: reading the message's facts (S1), gathering
the profile and the catalogue and building the report (S2), and the save
suggestions and quick-fill card (S7) — LLM and data reads stubbed."""

from __future__ import annotations

import json
from datetime import date

from app.domains.specialist.assessment import interface as assessment
from app.tools.specialist.assessment.s1_understanding import parser
from app.tools.specialist.assessment.s1_understanding.schema import StatedFacts
from app.tools.specialist.assessment.s2_assembly import builder, prefetch
from app.tools.specialist.assessment.s2_assembly.prefetched import Prefetched
from app.tools.specialist.assessment.s7_presentation import missing_info, save_suggestions

PROGRAMME = {
    "program_id": "nus_msc_dft", "is_target": True, "intake_year": 2027,
    "facts": {"toefl_ibt_min": 90, "toefl_ibt_band_min": 4.5, "ielts_min": 6, "gmat_gre_policy": "recommended",
              "gmat_gre_note": "The FAQ says a GMAT of about 700, or the GRE equivalent, is generally expected.",
              "work_exp_policy": "not_required", "programming_prereq": "conditional",
              "background_requirement": "A bachelor's degree in computing, or a related discipline."},
    "sources": {"toefl_ibt_min": [{"source_url": "https://adm", "role": "primary"}],
                "gmat_gre_policy": [{"source_url": "https://faq", "role": "primary"}]},
    "deadlines": [{"applicant_category": "all", "opens_on": date(2026, 10, 1), "closes_on": date(2027, 1, 31),
                   "source_url": "https://app"}],
}


def _prefetched(facts=None, sources=None, read=True, programme=PROGRAMME):
    return Prefetched(facts=facts or {}, fact_sources=sources or {}, programme=programme,
                      today=date(2026, 10, 16), profile_read=read)


# --- S1: what the message states ---------------------------------------------------

def test_only_values_that_fit_their_field_are_kept():
    raw = {"degree_discipline_category": "economics", "highest_degree": "master", "code_level": 7,
           "tech_stack": ["python", "rust"], "admission_tests": [{"key": "IELTS", "score": "6.5", "test_date": "2025-06"},
                                                                  {"key": "SAT", "score": 1500}],
           "english_medium_degree": "yes", "gpa_band": "first_class_equiv", "bachelor_grad_year": 2025}
    assert parser.clean(raw) == {
        "highest_degree": "master", "gpa_band": "first_class_equiv", "tech_stack": ["python"],
        "bachelor_grad_year": 2025,
        "admission_tests": [{"key": "IELTS", "score": 6.5, "test_date": "2025-06-01"}],
    }


def test_a_failed_parse_leaves_the_profile_to_carry_the_assessment(monkeypatch):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: "not json")
    assert parser.parse("I studied CS") == StatedFacts(parse_failed=True)


def test_the_parser_reads_the_message_into_profile_values(monkeypatch):
    seen = {}

    def complete(prompt, message, **kwargs):
        seen["prompt"] = prompt
        return json.dumps({"degree_discipline_category": "finance_econ_accounting", "code_level": 0})
    monkeypatch.setattr(parser.llm, "complete", complete)
    stated = parser.parse("经济学本科，不会编程")
    assert stated.values == {"degree_discipline_category": "finance_econ_accounting", "code_level": 0}
    assert "Never convert a numeric GPA" in seen["prompt"]


# --- S2: the report -------------------------------------------------------------

def test_the_message_is_laid_over_the_profile_with_each_facts_source():
    profile = {"degree_discipline_category": "business_mgmt", "tech_stack": ["excel_vba"],
               "admission_tests": [{"key": "IELTS", "score": 6.0, "test_date": "2025-01-01"},
                                   {"key": "GRE", "score": 320}],
               "certifications": [{"key": "cfa", "level": "L1"}]}
    stated = StatedFacts(values={"degree_discipline_category": "finance_econ_accounting", "tech_stack": ["python"],
                                 "admission_tests": [{"key": "IELTS", "score": 7.0, "test_date": "2026-05-01"}]})
    facts = builder.applicant_facts(_prefetched(profile, {"tech_stack": "CV", "certifications": "QA"}), stated)
    assert facts["degree_discipline_category"] == "finance_econ_accounting"
    assert facts["tech_stack"] == ["excel_vba", "python"]
    assert {t["key"]: t["score"] for t in facts["admission_tests"]} == {"IELTS": 7.0, "GRE": 320}
    assert facts["certifications"] == ["cfa"]
    assert facts["sources"]["degree_discipline_category"] == "message"
    assert facts["sources"]["certifications"] == "profile"


def test_the_requirements_come_from_the_catalogue_record():
    req = builder.requirements(PROGRAMME)
    assert (req["toefl_ibt_min"], req["toefl_band_min"], req["ielts_min"], req["gmat_reference"]) == (90, 4.5, 6, 700)
    assert (req["application_opens"], req["application_closes"]) == ("2026-10-01", "2027-01-31")
    assert req["source_urls"] == {"english": "https://adm", "gmat_gre": "https://faq", "deadline": "https://app"}


def test_without_the_catalogue_there_is_nothing_to_assess_against():
    assert builder.build_report(_prefetched(programme=None), StatedFacts()) is None


def test_the_built_report_runs_through_the_domain():
    stated = StatedFacts(values={"degree_discipline_category": "cs_se", "english_medium_degree": True})
    result = assessment.assess(builder.build_report(_prefetched(), stated))
    assert result["verdict"] == "all_met"


def test_prefetch_marks_an_unread_profile(monkeypatch):
    monkeypatch.setattr(prefetch, "_programme", lambda: PROGRAMME)
    monkeypatch.setattr(prefetch, "_profile", lambda uid: ({"code_level": 2}, {"code_level": "QA"}))
    monkeypatch.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: None)
    assert prefetch.prefetch("u1").profile_read
    monkeypatch.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    off = prefetch.prefetch("u1")
    assert not off.profile_read and off.consent_missing == "consent_personalized_rec"
    assert prefetch.CONSENT_OFF_NOTE in off.notes
    assert not prefetch.prefetch(None).profile_read


# --- S7: save suggestions and the card ---------------------------------------------

def test_new_or_changed_facts_are_offered_for_saving():
    profile = {"code_level": 1, "tech_stack": ["excel_vba"], "admission_tests": [{"key": "GRE", "score": 320}]}
    stated = StatedFacts(values={"code_level": 2, "tech_stack": ["excel_vba", "python"],
                                 "admission_tests": [{"key": "IELTS", "score": 7.0, "test_date": None}]})
    assert save_suggestions.save_suggestions(stated, _prefetched(profile)) == [
        {"field_key": "code_level", "value": 2},
        {"field_key": "tech_stack", "value": ["excel_vba", "python"]},
        {"field_key": "admission_tests", "value": [{"key": "GRE", "score": 320}, {"key": "IELTS", "score": 7.0}]},
    ]


def test_nothing_is_offered_on_an_unread_profile_or_for_what_it_already_holds():
    stated = StatedFacts(values={"code_level": 1, "tech_stack": ["python"]})
    assert save_suggestions.save_suggestions(stated, _prefetched({}, read=False)) == []
    assert save_suggestions.save_suggestions(stated, _prefetched({"code_level": 1, "tech_stack": ["python"]})) == []


def test_the_card_asks_for_the_open_fields_only_on_a_read_profile():
    card = missing_info.card(["degree_discipline_category", "english_medium_degree", "admission_tests"], _prefetched())
    assert [f["field_key"] for f in card["fields"]] == ["degree_discipline_category", "english_medium_degree"]
    assert card["kind"] == "quick_fill" and card["level"] == "supplementary"
    assert missing_info.card(["degree_discipline_category"], _prefetched(read=False)) is None


def test_a_degree_level_the_message_never_names_is_dropped(monkeypatch):
    reply = json.dumps({"highest_degree": "bachelor", "degree_discipline_category": "finance_econ_accounting"})
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: reply)
    assert "highest_degree" not in parser.parse("I studied economics").values
    assert parser.parse("I have a bachelor's in economics").values["highest_degree"] == "bachelor"
    assert parser.parse("经济学本科").values["highest_degree"] == "bachelor"


# --- S7: the render view, the check, the handler -------------------------------------

from app.tools.specialist.assessment import tool  # noqa: E402
from app.tools.specialist.assessment.s7_presentation import guardrail, payload, renderer  # noqa: E402


def _view(facts=None, labels=None):
    report = builder.build_report(_prefetched(), StatedFacts(values=facts or {}))
    prefetched = Prefetched(facts={}, fact_sources={}, programme=PROGRAMME, today=date(2026, 10, 16),
                            profile_read=True, value_labels=labels or {})
    return payload.to_render_view(assessment.assess(report), prefetched, notes=["note"])


def test_the_view_names_profile_values_and_keeps_the_disclaimer():
    view = _view({"degree_discipline_category": "finance_econ_accounting", "tech_stack": ["r", "python"]},
                 labels={"finance_econ_accounting": "Finance / economics / accounting", "r": "R", "python": "Python"})
    degree = next(c for c in view["hard_conditions"] if c["condition"] == "Degree background")
    assert "Finance / economics / accounting" in degree["finding"] and degree["status"] == "met"
    assert view["application_period"] == "August 2027 intake: 2026-10-01 to 2027-01-31"
    assert "not an admission decision" in view["disclaimer"] and view["notes"] == ["note"]
    assert view["based_on"] == "your message"


def test_the_check_catches_invented_figures_dates_odds_and_a_contradicted_verdict():
    view = _view({"degree_discipline_category": "finance_econ_accounting", "english_medium_degree": True})
    assert view["verdict"]["status"] == "to_confirm"
    assert guardrail.check("Applications close on 31 January 2027; IELTS 6 is the minimum.", view) == []
    assert any("figures" in v for v in guardrail.check("You need IELTS 7.5.", view))
    assert any("dates" in v for v in guardrail.check("Apply by March 2027.", view))
    assert any("odds" in v for v in guardrail.check("You have a 70% chance.", view))
    assert any("odds" in v for v in guardrail.check("你的录取概率很高。", view))
    assert any("every requirement" in v for v in guardrail.check("You meet all the requirements.", view))
    assert guardrail.check("有戏吗？我觉得可以。", view, user_message="申请有戏吗") == []
    assert guardrail.check("Strength: coursework in Probability & statistics.", view) == []
    assert any("odds" in v for v in guardrail.check("The probability of admission is high.", view))


def test_a_reply_failing_the_check_twice_falls_back_to_the_template(monkeypatch):
    view = _view({"degree_discipline_category": "cs_se"})
    replies = iter(["You have a 90% chance.", "Admission is guaranteed."])
    monkeypatch.setattr(renderer, "render_structured_reply", lambda *a, **k: (next(replies), view["sources"]))
    text, _ = renderer.render(view, "am I ready?")
    assert "Hard conditions" in text or "Verdict" in text


def test_the_handler_assesses_and_offers_suggestions_and_the_card(monkeypatch):
    prefetched = Prefetched(facts={"code_level": 1}, fact_sources={}, programme=PROGRAMME,
                            today=date(2026, 10, 16), profile_read=True)
    monkeypatch.setattr(tool, "prefetch", lambda uid: prefetched)
    monkeypatch.setattr(tool.parser, "parse",
                        lambda message: StatedFacts(values={"degree_discipline_category": "finance_econ_accounting"}))
    seen = {}

    def render(view, message, **kwargs):
        seen["view"], seen["kwargs"] = view, kwargs
        return "reply", view["sources"]
    monkeypatch.setattr(tool.renderer, "render", render)
    from app.tools.turn_context import TurnState
    from langchain_core.messages import HumanMessage
    answer = tool._handler(TurnState(messages=[HumanMessage("I studied economics")], user_id="u1",
                                     reply_language="zh", other_tools=("financial",)))
    assert answer.text == "reply" and answer.agent_used == "assessment_agent"
    assert answer.save_suggestions == [{"field_key": "degree_discipline_category", "value": "finance_econ_accounting"}]
    assert answer.supplement_card["kind"] == "quick_fill"
    assert seen["kwargs"]["language"] == "zh" and seen["kwargs"]["other_tools"] == ("financial",)
    assert answer.contexts[0]["tool"] == "assessment"
    assert tool.ASSESSMENT_TOOL.skip_evaluation


def test_without_the_catalogue_the_handler_says_it_cannot_assess(monkeypatch):
    monkeypatch.setattr(tool, "prefetch", lambda uid: _prefetched(programme=None))
    monkeypatch.setattr(tool.parser, "parse", lambda message: StatedFacts())
    from app.tools.turn_context import TurnState
    from langchain_core.messages import HumanMessage
    answer = tool._handler(TurnState(messages=[HumanMessage("am I ready?")], user_id=None))
    assert answer.agent_used == "assessment_agent_unavailable"


def test_an_invented_whole_number_test_score_is_caught_too():
    view = _view({"degree_discipline_category": "cs_se"})
    assert any("figures" in v for v in guardrail.check("You need IELTS 7 overall.", view))
    assert guardrail.check("Step 2 of 3: check IELTS 6.", view) == []
