"""Exercises the tool's s7_presentation/: the render view keeps audit data
out of the rendering model's input, the guardrail catches invented course
codes and wrong unit counts, and the renderer re-renders once and then
falls back to the template. The rendering model is always stubbed."""

from __future__ import annotations

from app.tools.specialist.course_recommendation.s7_presentation import guardrail, renderer
from app.tools.specialist.course_recommendation.s7_presentation.payload import to_render_view

RESULT = {
    "request_id": "r1",
    "workflow_status": "degraded",
    "target_role": "Data Analytics",
    "groups": [{
        "slot_id": "core_mandatory", "slot_type": "core_mandatory", "label": "Mandatory core courses",
        "required_pick_count": 1, "note": None,
        "recommendations": [{
            "course_code": "IT5006", "course_title": "Fundamentals of Data Analytics", "units": 4,
            "section": "Core", "vertical": [], "level": 5000, "offered_terms": ["Semester 1 (2026-2027)"],
            "course_time": None, "workload": None, "matched_skills": ["data_analytics"],
            "reason": "Closes skill gaps: data_analytics.", "caution": None, "recommended": True,
            "score_breakdown": [{"signal": "skill_gap", "delta": 2.0, "evidence": "closes skill gaps: data_analytics"}],
            "synopsis": "A foundation in data analytics: exploratory data analysis and predictive modeling.",
            "evidence": ["one of the 2 mandatory core courses you still need",
                         "tagged for your target role, Data Analytics"],
        }],
    }],
    "degree_progress": {"core_mandatory_done": ["IT5001X"], "core_mandatory_remaining": ["IT5006"],
                        "total_units_done": 4, "total_units_target": 52, "elective_level4000_used": 0},
    "skill_gaps": ["data_analytics"],
    "completed_recognized": ["IT5001X"],
    "completed_unrecognized": [],
    "completed_units": 4,
    "notes": ["Some note."],
    "sources": ["https://nusmods.com/courses/IT5006"],
    "diagnostics": [{"stage": "role_resolution", "code": "X", "message": "m", "retryable": False}],
    "stage_results": [{"sequence": 1, "stage": "input_validation"}],
}


def test_view_keeps_what_the_reply_needs_and_drops_audit_data():
    view = to_render_view(RESULT)
    assert set(view) == {"target_role", "groups", "degree_progress", "skill_gaps", "notes", "sources"}
    course = view["groups"][0]["courses"][0]
    assert course["course_code"] == "IT5006" and course["units"] == 4 and course["recommended"] is True
    assert course["synopsis"].startswith("A foundation in data analytics")
    assert course["evidence"][1] == "tagged for your target role, Data Analytics"
    assert not {"score_breakdown", "reason", "matched_skills"} & set(course)
    assert "elective_level4000_used" not in view["degree_progress"]


def test_guardrail_accepts_a_faithful_reply():
    view = to_render_view(RESULT)
    reply = "Take IT5006 (4 units) next — you've already done IT5001X."
    assert guardrail.check(reply, view) == []


def test_guardrail_flags_an_invented_course_code():
    view = to_render_view(RESULT)
    assert guardrail.check("Take IT5006 and FT5011.", view) == ["course codes not in the result: FT5011"]


def test_guardrail_flags_a_wrong_unit_count():
    view = to_render_view(RESULT)
    assert guardrail.check("IT5006 – Fundamentals of Data Analytics, 6 units", view) == [
        "IT5006 is 4 units, the reply says 6"
    ]


def test_guardrail_ignores_numbers_on_the_next_line():
    view = to_render_view(RESULT)
    assert guardrail.check("Take IT5006.\nYou have 48 units left.", view) == []


def test_renderer_rerenders_once_then_uses_the_template(monkeypatch):
    calls = []

    def _render(view, msg, prompt, on_event=None, depth=None):
        calls.append((prompt, on_event))
        return "Take FT9999.", view["sources"]

    monkeypatch.setattr(renderer, "render_structured_reply", _render)
    sentinel = object()
    reply, sources = renderer.render(RESULT, "courses?", on_event=sentinel)

    assert len(calls) == 2
    assert calls[0][1] is sentinel and calls[1][1] is None  # the retry never streams
    assert "FT9999" in calls[1][0]  # the retry is told what was wrong
    assert "IT5006" in reply and "FT9999" not in reply  # template reply
    assert sources == ["https://nusmods.com/courses/IT5006"]


def test_renderer_keeps_a_corrected_retry(monkeypatch):
    replies = iter(["Take FT9999.", "Take IT5006 (4 units)."])
    monkeypatch.setattr(renderer, "render_structured_reply",
                        lambda view, msg, prompt, on_event=None, depth=None: (next(replies), []))
    assert renderer.render(RESULT, "courses?")[0] == "Take IT5006 (4 units)."
