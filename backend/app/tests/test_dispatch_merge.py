"""dispatch/merge.py: a multi-tool turn's drafts are joined in
classification order with nothing rewritten — no LLM call."""

from __future__ import annotations

from app.orchestrator.dispatch import merge
from app.tools.contracts import ToolAnswer


def test_drafts_are_joined_in_order_without_rewriting():
    partials = [
        ("course_recommendation", ToolAnswer(text="Take FT5005.", sources=["nusmods"], agent_used="course_agent")),
        ("financial", ToolAnswer(text="Tuition is S$76,409.", sources=["fees page", "nusmods"],
                                 agent_used="financial_agent")),
    ]
    answer = merge.merge(partials)
    assert answer.text == "Take FT5005.\n\n---\n\nTuition is S$76,409."
    assert answer.sources == ["nusmods", "fees page"]
    assert answer.agent_used == "course_agent+financial_agent"
    assert not answer.needs_clarification


def test_empty_drafts_are_left_out_and_suggestions_kept():
    partials = [("a", ToolAnswer(text="  ", agent_used="a")),
                ("b", ToolAnswer(text="B", save_suggestions=[{"field_key": "x", "value": 1}], agent_used="b"))]
    answer = merge.merge(partials)
    assert answer.text == "B" and answer.save_suggestions == [{"field_key": "x", "value": 1}]


def test_the_reply_asks_for_clarification_only_when_every_draft_does():
    ask = ToolAnswer(text="Which role?", needs_clarification=True, card={"kind": "quick_fill"})
    answer = ToolAnswer(text="Tuition is S$76,409.")
    mixed = merge.merge([("career", ask), ("financial", answer)])
    assert not mixed.needs_clarification and mixed.card == {"kind": "quick_fill"}
    assert merge.merge([("career", ask), ("career2", ask)]).needs_clarification


def test_the_shared_message_line_names_the_other_parts():
    from app.core import shared_turn
    line = shared_turn.instruction(("financial", "career"))
    assert "fees and funding, career planning" in line and "Answer only your own part" in line
    assert shared_turn.instruction(()) == "" and shared_turn.with_instruction("P", ()) == "P"


def test_the_shared_message_line_says_who_owns_an_overlapping_point():
    from app.core import shared_turn
    line = shared_turn.instruction(("comparison",))
    assert "anything about another programme" in line and "fees" in line
    assert "overlap" not in shared_turn.instruction(("faq",))


PASS = ("The School of Computing applies for a single-journey visa cum in-principle Student's Pass "
        "approval on your behalf through SOLAR, and tells you in writing how to finish the process.")


def test_a_later_draft_drops_a_paragraph_an_earlier_one_already_said():
    first = ToolAnswer(text=f"Accept the offer in GDA.\n\n{PASS}", agent_used="admissions_agent")
    second = ToolAnswer(text=f"Tuition is S$76,409.\n\n{PASS.replace('tells', 'informs')}", agent_used="financial_agent")
    answer = merge.merge([("admissions", first), ("financial", second)])
    assert answer.text.count("single-journey visa") == 1 and "Tuition is S$76,409." in answer.text


def test_a_draft_that_only_repeats_is_left_out_and_short_lines_stay():
    first = ToolAnswer(text=PASS)
    answer = merge.merge([("admissions", first), ("faq", ToolAnswer(text=PASS)),
                          ("financial", ToolAnswer(text="Student's Pass\n\nTuition is S$76,409."))])
    assert answer.text == f"{PASS}\n\n---\n\nStudent's Pass\n\nTuition is S$76,409."
