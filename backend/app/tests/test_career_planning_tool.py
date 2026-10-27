"""Exercises the career planning tool's gate, S1 parser, S2 prefetch and
builder, and the handler that sequences them. Data reads and the model are
stubbed; no database, no LLM."""

from __future__ import annotations

import json
from datetime import date

import pytest
from langchain_core.messages import HumanMessage

from app.tools import input_needs as shared
from app.tools.specialist.career_planning import gate, tool
from app.tools.specialist.career_planning.s1_understanding import parser
from app.tools.specialist.career_planning.s1_understanding.schema import ParsedCareerRequest
from app.tools.specialist.career_planning.s2_assembly import builder, prefetch
from app.tools.specialist.career_planning.s2_assembly.prefetched import Prefetched
from app.tools.turn_context import PreviousTurn, TurnState

CATALOG = [
    {"tag": "data_analytics", "name": "Data Analytics", "definition": "Insight from data.",
     "required_skills": ["data_analytics", "programming", "finance"]},
    {"tag": "data_engineering", "name": "Data Engineering", "definition": "Pipelines.",
     "required_skills": ["data_engineering", "programming", "data_analytics"]},
    {"tag": "quantitative_finance", "name": "Quantitative Finance", "definition": "Pricing.",
     "required_skills": ["programming", "finance", "risk_modeling", "data_analytics"]},
]
LINKS = [{"code": "FT5005", "title": "ML for Finance", "tags": ["data_analytics", "quantitative_finance"]}]


def _state(**kw) -> TurnState:
    message = kw.pop("message", "career?")
    return TurnState(messages=[HumanMessage(message)], user_id=kw.pop("user_id", "u1"), **kw)


def _prefetched(facts=None, **kw) -> Prefetched:
    return Prefetched(facts=facts or {}, stage=kw.pop("stage", "current"), readiness_gaps=kw.pop("gaps", []),
                      role_catalog=CATALOG, course_links=LINKS, **kw)


# --- gate ---

@pytest.fixture
def profile(monkeypatch):
    facts: dict = {}
    seen = {"stage": "current", "consent": None}
    monkeypatch.setattr(gate, "get_profile_for_purpose", lambda uid, purpose: facts)
    monkeypatch.setattr(gate, "get_profile_field", lambda uid, key: seen["stage"])
    monkeypatch.setattr(gate, "missing_purpose_consent", lambda uid, purpose: seen["consent"])
    monkeypatch.setattr(shared, "missing_purpose_consent", lambda uid, purpose: seen["consent"])
    return facts, seen


def _levels(needs) -> dict:
    return {n.field_key or n.slot: n.level for n in needs}


def test_a_plan_without_a_role_offers_it_and_explores(profile):
    assert _levels(gate.input_needs(_state(career_mode_hint="plan"))) == {
        "main_target_role": "optional", "function_experience": "optional", "target_markets": "supplementary",
    }


def test_a_plan_with_a_role_offers_timing_and_markets_alongside(profile):
    facts, _ = profile
    facts.update(main_target_role="data_analytics")
    assert _levels(gate.input_needs(_state(career_mode_hint="plan"))) == {
        "job_search_timeline": "supplementary", "target_markets": "supplementary",
        "internship_status": "supplementary",
    }


def test_a_prospect_isnt_asked_about_job_search_or_internships(profile):
    facts, seen = profile
    facts.update(main_target_role="data_analytics")
    seen["stage"] = "prospect"
    assert _levels(gate.input_needs(_state(career_mode_hint="plan"))) == {"target_markets": "supplementary"}


def test_a_role_in_the_message_counts_as_given(profile):
    needs = _levels(gate.input_needs(_state(career_mode_hint="plan", target_role_hint="quant")))
    assert "main_target_role" not in needs and "job_search_timeline" in needs


def test_exploration_asks_for_experience_only_without_any_evidence(profile):
    facts, _ = profile
    assert "function_experience" in _levels(gate.input_needs(_state(career_mode_hint="exploration")))
    facts.update(code_level=3)
    assert _levels(gate.input_needs(_state(career_mode_hint="exploration"))) == {"target_markets": "supplementary"}


def test_compare_asks_nothing_the_message_may_already_name_the_roles(profile):
    assert gate.input_needs(_state(career_mode_hint="compare", message="data analyst or data engineer?")) == ()


def test_without_consent_plans_ask_for_it_and_comparisons_run(profile):
    _, seen = profile
    seen["consent"] = "consent_personalized_rec"
    (need,) = gate.input_needs(_state(career_mode_hint="plan"))
    assert (need.consent_key, need.level) == ("consent_personalized_rec", "required")
    assert gate.input_needs(_state(career_mode_hint="compare")) == ()


def test_an_anonymous_user_is_asked_nothing(profile):
    assert gate.input_needs(_state(user_id=None)) == ()


# --- S1 parser ---

def _reply(monkeypatch, payload):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: json.dumps(payload))


def test_the_parser_maps_roles_onto_the_catalogue(monkeypatch):
    _reply(monkeypatch, {"roles": ["quantitative_finance", "astronaut", "data_analytics"],
                         "unmatched_roles": ["pilot"], "job_search_timeline": "right_after",
                         "internship_status": "maybe", "target_markets": ["SG", "MARS"]})
    parsed = parser.parse("quant or data analyst? I'd also like to fly", CATALOG)
    assert parsed.roles == ["quantitative_finance", "data_analytics"]
    assert parsed.unmatched_roles == ["pilot"]
    assert (parsed.job_search_timeline, parsed.internship_status) == ("right_after", None)
    assert parsed.target_markets == ["SG"]


def test_the_parser_gives_the_model_the_catalogue(monkeypatch):
    seen = {}
    monkeypatch.setattr(parser.llm, "complete", lambda prompt, *a, **k: seen.setdefault("prompt", prompt) and "{}")
    parser.parse("which roles fit me?", CATALOG)
    assert "- quantitative_finance: Quantitative Finance — Pricing." in seen["prompt"]


def test_a_failed_parse_is_marked(monkeypatch):
    monkeypatch.setattr(parser.llm, "complete", lambda *a, **k: "not json")
    assert parser.parse("x", CATALOG).parse_failed
    assert parser.parse("  ", CATALOG) == ParsedCareerRequest()


# --- S2 builder ---

@pytest.mark.parametrize("hint, named, profile_roles, mode, roles, noted", [
    ("plan", ["quantitative_finance"], ["data_analytics"], "plan", ["quantitative_finance"], False),
    ("plan", [], ["data_analytics"], "plan", ["data_analytics"], False),
    ("plan", [], [], "exploration", [], True),
    ("compare", ["data_analytics", "data_engineering"], [], "compare", ["data_analytics", "data_engineering"], False),
    ("compare", ["quantitative_finance"], ["data_analytics"], "compare",
     ["quantitative_finance", "data_analytics"], False),
    ("compare", ["quantitative_finance"], [], "plan", ["quantitative_finance"], True),
    ("compare", [], [], "exploration", [], True),
    # Picking a role out of an exploration asks for its plan.
    ("exploration", ["data_analytics"], [], "plan", ["data_analytics"], False),
    ("exploration", ["data_analytics", "data_engineering"], [], "compare",
     ["data_analytics", "data_engineering"], False),
    ("exploration", [], ["data_analytics"], "exploration", [], False),
    (None, ["data_analytics", "data_engineering"], [], "compare", ["data_analytics", "data_engineering"], False),
    (None, [], ["data_engineering"], "plan", ["data_engineering"], False),
    (None, [], [], "exploration", [], False),
])
def test_the_mode_and_roles_that_run(hint, named, profile_roles, mode, roles, noted):
    facts = {"target_role_families": profile_roles} if profile_roles else {}
    resolved = builder.resolve_mode(hint, ParsedCareerRequest(roles=named), _prefetched(facts))
    assert resolved[:2] == (mode, roles)
    # A fallback (not what was asked for) says what ran instead.
    assert bool(resolved[2]) == noted


def test_the_report_maps_profile_facts_and_lets_the_message_win():
    facts = {
        "code_level": 3, "tech_stack": ["python"], "target_markets": ["CN"], "job_search_timeline": "right_after",
        "function_experience": [{"key": "data_ai", "internship": True}, "engineering"],
        "current_modules": [{"term": "AY2026/27 Sem1", "course_code": "FT5005"}],
        "expected_grad_term": "AY2027/28 Sem1", "main_target_role": "data_analytics", "languages": ["en"],
    }
    parsed = ParsedCareerRequest(target_markets=["SG"], internship_status="searching")
    built = builder.build_report(_prefetched(facts, gaps=[{"area": "finance", "level": 0, "required": 1}]),
                                 parsed, "plan", date(2026, 10, 13), "u1")
    report = built.report
    assert report["profile"] == {
        "code_level": 3, "tech_stack": ["python"],
        "function_experience": [{"key": "data_ai", "internship": True}, {"key": "engineering"}],
        "completed_courses": [], "current_courses": ["FT5005"],
    }
    assert report["situation"] == {
        "expected_grad_term": "AY2027/28 Sem1", "stage": "current", "job_search_timeline": "right_after",
        "internship_status": "searching", "target_markets": ["SG"],
    }
    assert report["target_roles"] == ["data_analytics"] and report["preferred_roles"] == ["data_analytics"]
    assert report["readiness_gaps"] == [{"area": "finance", "level": 0, "required": 1}]
    assert report["evidence_sources"] == list(builder.SOURCES)


def test_certifications_reach_the_report_as_keys_marking_exams_in_progress():
    # The profile stores certifications as {key, level}; the planner's contract takes keys,
    # and a CFA level or FRM Part 1 passed is not the credential itself.
    facts = {"certifications": [{"key": "cfa", "level": "L2"}, {"key": "frm", "level": "Part 1"}, "pmp",
                                {"key": "cfa", "level": "Charterholder"}]}
    report = builder.build_report(_prefetched(facts), ParsedCareerRequest(), "exploration", date(2026, 10, 13)).report
    assert report["profile"]["certifications"] == ["cfa_partial", "frm_partial", "pmp", "cfa"]


def test_the_reply_names_a_certification_with_its_level(monkeypatch):
    monkeypatch.setattr(prefetch, "field_labels", lambda keys: {"certifications": "Certifications"})
    monkeypatch.setattr(prefetch, "describe_value", lambda key, value: str(value).upper())
    labels = prefetch.evidence_labels({"certifications": [{"key": "cfa", "level": "L2"},
                                                          {"key": "cloud_cert", "level": "AWS Solutions Architect"}]})
    assert labels["certifications"]["values"] == {
        "cfa_partial": "CFA (L2 passed — exams in progress, credential not yet held)",
        "cloud_cert": "CLOUD_CERT (AWS Solutions Architect)",
    }


def test_unmatched_roles_and_a_failed_parse_are_noted():
    built = builder.build_report(_prefetched(), ParsedCareerRequest(unmatched_roles=["pilot"], parse_failed=True),
                                 "exploration", date(2026, 10, 13))
    assert any('"pilot"' in n for n in built.notes) and any("couldn't be made out" in n for n in built.notes)


def test_profile_roles_ignore_unknown_tags():
    facts = {"main_target_role": "astronaut", "target_role_families": ["data_engineering", "data_engineering"]}
    assert _prefetched(facts).profile_roles == ["data_engineering"]


# --- S2 prefetch ---

@pytest.fixture
def reads(monkeypatch):
    monkeypatch.setattr(prefetch, "list_role_tags", lambda: [
        {"tag": "data_analytics", "name_en": "Data Analytics", "definition": "d", "required_skills": ["finance"]},
        {"tag": "empty", "name_en": "Empty", "definition": None, "required_skills": []},
    ])
    monkeypatch.setattr(prefetch, "list_courses", lambda: [
        {"course_code": "FT5005", "title": "ML", "can_recommend": True},
        {"course_code": "FT5007", "title": "Capstone", "can_recommend": False},
    ])
    monkeypatch.setattr(prefetch, "list_course_tags", lambda: {"FT5005": ["data_analytics"], "FT5007": ["x"]})
    monkeypatch.setattr(prefetch, "get_profile_for_purpose", lambda uid, purpose: {"code_level": 2})
    monkeypatch.setattr(prefetch, "get_profile_field", lambda uid, key: "current")
    monkeypatch.setattr(prefetch, "derived_readiness_gaps", lambda uid: [])
    monkeypatch.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: None)
    return monkeypatch


def test_prefetch_gathers_the_turns_data(reads):
    got = prefetch.prefetch("u1")
    assert got.facts == {"code_level": 2} and got.stage == "current" and got.profile_read
    assert [r["tag"] for r in got.role_catalog] == ["data_analytics"]   # roles without skills are left out
    assert got.course_links == [{"code": "FT5005", "title": "ML", "tags": ["data_analytics"]}]
    assert got.notes == ()


def test_a_profile_read_failure_is_noted_not_fatal(reads):
    def broken(*a):
        raise RuntimeError("db down")
    reads.setattr(prefetch, "get_profile_for_purpose", broken)
    got = prefetch.prefetch("u1")
    assert got.facts == {} and any("couldn't be read" in n for n in got.notes)
    assert not got.profile_read


def test_missing_consent_is_noted(reads):
    reads.setattr(prefetch, "missing_purpose_consent", lambda uid, purpose: "consent_personalized_rec")
    got = prefetch.prefetch("u1")
    assert any("turned off" in n for n in got.notes) and not got.profile_read


def test_an_unknown_consent_state_does_not_count_as_read(reads):
    def broken(*a):
        raise RuntimeError("db down")
    reads.setattr(prefetch, "missing_purpose_consent", broken)
    got = prefetch.prefetch("u1")
    assert got.facts == {"code_level": 2} and not got.profile_read
    assert not any("turned off" in n for n in got.notes)


def test_signed_out_users_have_no_profile_read(reads):
    assert not prefetch.prefetch(None).profile_read


def test_a_knowledge_base_failure_propagates(reads):
    def broken():
        raise RuntimeError("kb down")
    reads.setattr(prefetch, "list_role_tags", broken)
    with pytest.raises(RuntimeError):
        prefetch.prefetch("u1")


# --- handler ---

def test_the_handler_runs_the_steps_and_puts_the_notes_first(monkeypatch):
    monkeypatch.setattr(tool, "role_catalog", lambda: CATALOG)
    monkeypatch.setattr(tool.parser, "parse",
                        lambda message, catalog, options: ParsedCareerRequest(roles=["data_analytics"]))
    monkeypatch.setattr(tool, "prefetch",
                        lambda uid: _prefetched({"code_level": 3}, notes=("Profile note.",), profile_read=True))
    seen = {}

    def render(result, prefetched, message, on_event=None, depth=None, language=None, other_tools=(), repeat=False):
        seen["result"], seen["repeat"] = result, repeat
        return "reply", ["src"]
    monkeypatch.setattr(tool.renderer, "render", render)

    answer = tool._handler(_state(career_mode_hint="plan", message="am I ready for data analytics?"))
    assert answer.text == "reply" and answer.agent_used == "career_agent"
    assert answer.save_suggestions == [{"field_key": "main_target_role", "value": "data_analytics"}]
    result = seen["result"]
    assert result["mode"] == "plan" and result["roles"][0]["role"]["tag"] == "data_analytics"
    assert result["notes"][0] == "Profile note."
    assert result["roadmap"]["phases"]
    assert answer.contexts == [{"tool": "career", "mode": "plan", "subjects": ["data_analytics"], "awaiting": None}]
    assert seen["repeat"] is False


def test_the_handler_reads_a_pick_from_the_roles_it_offered(monkeypatch):
    options = [{"key": "data_analytics", "label": "Data Analytics"}]
    previous = PreviousTurn(user_message="what fits me?", reply="Which one?", contexts=(
        {"tool": "career", "mode": "exploration", "subjects": ["data_analytics"],
         "awaiting": {"kind": "choose_role", "options": options}},))
    monkeypatch.setattr(tool, "role_catalog", lambda: CATALOG)
    seen = {}

    def parse(message, catalog, offered):
        seen["options"] = offered
        return ParsedCareerRequest(roles=["data_analytics"])
    monkeypatch.setattr(tool.parser, "parse", parse)
    monkeypatch.setattr(tool, "prefetch", lambda uid: _prefetched({"code_level": 3}))
    monkeypatch.setattr(tool.renderer, "render", lambda *a, **k: ("reply", []))
    answer = tool._handler(_state(career_mode_hint="exploration", message="the first one", previous_turn=previous))
    assert seen["options"] == options
    assert answer.contexts[0]["mode"] == "plan"


@pytest.mark.parametrize("message", ["I'd start job hunting right after graduating.", "我打算毕业后找工作"])
def test_a_timeline_stated_in_the_message_isnt_asked_for(profile, message):
    facts, _ = profile
    facts.update(main_target_role="data_analytics")
    assert "job_search_timeline" not in _levels(gate.input_needs(_state(career_mode_hint="plan", message=message)))


def test_the_parser_is_told_which_roles_were_offered(monkeypatch):
    seen = {}
    monkeypatch.setattr(parser.llm, "complete", lambda prompt, *a, **k: seen.setdefault("prompt", prompt) and "{}")
    parser.parse("第二个", CATALOG, [{"key": "data_analytics", "label": "Data Analytics"},
                                   {"key": "data_engineering", "label": "Data Engineering"}])
    assert "1. Data Analytics (data_analytics)\n2. Data Engineering (data_engineering)" in seen["prompt"]
    assert "by position" in seen["prompt"]


def test_the_parser_lists_each_roles_chinese_name(monkeypatch):
    seen = {}
    monkeypatch.setattr(parser.llm, "complete", lambda prompt, *a, **k: seen.setdefault("prompt", prompt) and "{}")
    catalog = [{**CATALOG[1], "name_zh": "数据工程"}]
    parser.parse("那和数据工程比呢？", catalog)
    assert "- data_engineering: Data Engineering / 数据工程 — Pipelines." in seen["prompt"]


def test_a_comparison_follow_up_compares_against_the_previous_role():
    # "And compared with data engineering?" after a data analytics plan.
    resolved = builder.resolve_mode("compare", ParsedCareerRequest(roles=["data_engineering"]),
                                    _prefetched({"main_target_role": "quantitative_finance"}),
                                    previous_roles=["data_analytics"])
    assert resolved == ("compare", ["data_engineering", "data_analytics", "quantitative_finance"], [])


def test_the_report_carries_only_the_contracts_role_fields():
    prefetched = Prefetched(facts={}, stage=None, readiness_gaps=[], course_links=LINKS,
                            role_catalog=[{**r, "name_zh": "x"} for r in CATALOG])
    report = builder.build_report(prefetched, ParsedCareerRequest(), "exploration", date(2026, 10, 13)).report
    assert all("name_zh" not in r for r in report["role_catalog"])
