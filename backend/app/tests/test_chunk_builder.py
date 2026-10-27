"""Pins domains/knowledge_retrieval/chunk_builder.py to the exact shape of
the structured chunks already in knowledge.document_chunks (the expected
strings are copied from the live rows; a read-only comparison rebuilt all
89 of them identically when the builder was written)."""

from __future__ import annotations

from decimal import Decimal

from app.domains.knowledge_retrieval import chunk_builder as cb

PROGRAMME = "the NUS MSc Digital Financial Technology (MSc DFinTech)"


def test_admission_items():
    chunk = cb.admission_item({
        "key": "cv", "label": "Curriculum Vitae / CV", "required": True, "deadline_key": "application_deadline",
        "why": "Summarises your education, work/internship experience, projects, achievements and readiness for the programme.",
    })
    assert chunk.chunk_key == "admission:cv"
    assert chunk.content == ("Curriculum Vitae / CV — Required. Summarises your education, work/internship "
                             "experience, projects, achievements and readiness for the programme.")
    assert chunk.context == (f'Application document requirement for {PROGRAMME}: "Curriculum Vitae / CV". '
                             "Useful for the application checklist and what to submit.")
    assert chunk.metadata == {"required": True, "deadline_key": "application_deadline"}
    assert chunk.token_count == 43


def test_optional_admission_items_say_so():
    chunk = cb.admission_item({"key": "x", "label": "GRE", "required": False, "why": "Useful.", "deadline_key": None})
    assert chunk.content == "GRE — Optional or conditional. Useful."


def test_application_statuses_with_and_without_an_eta():
    review = cb.application_status({
        "status_code": "UNDER_REVIEW", "human_status": "Materials complete; application under review",
        "next_step": "No action is needed. A decision is expected within 2–3 weeks.", "eta_days": 21,
    })
    assert review.content == ('Application status "Materials complete; application under review". Next step: No action '
                              "is needed. A decision is expected within 2–3 weeks. (typically about 21 days).")
    assert review.metadata == {"eta_days": 21, "status_code": "UNDER_REVIEW"}
    draft = cb.application_status({
        "status_code": "DRAFT", "human_status": "Application not submitted yet (draft) ",
        "next_step": "Complete all required fields and submit the application.", "eta_days": None,
    })
    assert draft.content == ('Application status "Application not submitted yet (draft)". '
                             "Next step: Complete all required fields and submit the application.")
    assert draft.metadata == {"status_code": "DRAFT"}


def test_courses_keep_the_metadata_only_the_chunk_has():
    chunk = cb.course(
        {"course_code": "FT5010", "title": "Data-driven Investing", "module_credit": Decimal("4"),
         "department": "Information Systems and Analytics", "status": "active", "annex_section": "Core Courses",
         "annex_intake": "2026", "description": "Covers investing.",
         "prerequisite": "Must have completed IT5001 or IT5001X", "preclusion": "IS4226"},
        [{"tag": "risk_management", "name_zh": "风险管理"}, {"tag": "data_analytics", "name_zh": "数据分析"}],
        {"faculty": "Computing", "source_url": "https://example/FT5010.json", "can_recommend": True, "status": "inactive"},
    )
    assert chunk.content == (
        "FT5010 Data-driven Investing (4 units). Faculty: Computing, Information Systems and Analytics. "
        "Description: Covers investing. Prerequisite: Must have completed IT5001 or IT5001X Preclusion: IS4226 "
        "Topic tags: data_analytics (数据分析); risk_management (风险管理)."
    )
    assert chunk.context.startswith('This describes course FT5010 "Data-driven Investing", a 4-unit course relevant to')
    assert chunk.metadata == {
        "faculty": "Computing", "source_url": "https://example/FT5010.json", "can_recommend": True,
        "status": "active", "department": "Information Systems and Analytics",
        "annex_intake": "2026", "annex_section": "Core Courses",
    }


def test_course_metadata_leaves_out_empty_fields():
    chunk = cb.course(
        {"course_code": "IT5001", "title": "T", "module_credit": 4, "department": "CS", "status": "active",
         "annex_section": None, "annex_intake": "2025", "description": None, "prerequisite": None, "preclusion": None},
        [], {"faculty": "Computing", "annex_section": "old"},
    )
    assert "annex_section" not in chunk.metadata
    assert chunk.content == "IT5001 T (4 units). Faculty: Computing, CS."


def test_course_rules():
    chunk = cb.course_rule({"id": "cur_core", "intake": "2026-08-onwards", "category": "core", "text": "Rule text."})
    assert (chunk.chunk_key, chunk.content) == ("rule:cur_core", "Rule text.")
    assert chunk.context == f"Curriculum rule (core) for {PROGRAMME}, applicable to the 2026-08-onwards intake."


def test_the_embedding_text_is_context_then_content():
    chunk = cb.course_rule({"id": "r", "intake": "i", "category": "c", "text": "T."})
    assert chunk.embedding_text == f"{chunk.context}\nT."


def test_reload_catalogue_clears_cached_retrievals_and_survives_a_cache_outage(monkeypatch):
    from app.domains.knowledge_retrieval import service

    cleared, invalidated = [], []
    monkeypatch.setattr(service.knowledge_db, "invalidate", lambda: invalidated.append(True))

    class _Cache:
        def delete_prefix(self, prefix):
            cleared.append(prefix)
            return 3

    monkeypatch.setattr(service, "cache", _Cache())
    service.reload_catalogue()
    assert (invalidated, cleared) == ([True], ["rag:retrieve:"])

    class _DownCache:
        def delete_prefix(self, prefix):
            raise ConnectionError("redis down")

    monkeypatch.setattr(service, "cache", _DownCache())
    service.reload_catalogue()  # must not raise
    assert invalidated == [True, True]
