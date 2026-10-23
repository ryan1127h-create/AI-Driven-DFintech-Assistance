"""
Alumni match tool — "can you connect me with alumni in digital payments?"
answered with the student's best alumni matches from the Alumni Match
directory: the same listing, ranking and privacy as the Alumni Match page
(alumni domain's list_matches), the top few shown as a card with a link to
each one there. No LLM call and no request sent from the chat: the student
sends it on the page, where they see what the alumnus will be shown.

Only enrolled students reach it — the stage policy answers everyone else
(app/core/stage_policy.py).
"""

from __future__ import annotations

from app.domains.alumni import interface as alumni
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.turn_context import ChatToolInput, TurnState

_SHOWN = 3
_REQUEST_LABELS = {"pending": "Request sent", "accepted": "Connected"}


def _line(person: dict) -> str:
    year = f", class of {person['class_year']}" if person.get("class_year") else ""
    expertise = ", ".join(e["label"] for e in person["expertise"])
    status = _REQUEST_LABELS.get((person.get("request") or {}).get("status"))
    return (f"- **{person['name']}** — {person['position']}, {person['company']}{year}. Expertise: {expertise}."
            + (f" ({status})" if status else ""))


def build_answer(result: dict, wanted: str | None, wanted_label: str | None, filtered: bool) -> ToolAnswer:
    """The reply and card for `result` (list_matches' output). `filtered`:
    the listing was narrowed to `wanted` (a role tag) and found someone."""
    people = result["items"][:_SHOWN]
    if not people:
        text = ("There are no alumni listed in the Alumni Match directory yet. New alumni join it over time — "
                "check Alumni Match again later.")
        return ToolAnswer(text=text, agent_used="alumni_agent")
    if filtered:
        intro = f"Here are alumni working in {wanted_label}:"
    elif wanted:
        intro = (f"No listed alumni have {wanted_label} as their expertise yet, so here are the closest matches "
                 "to your goals instead:")
    elif result.get("ranked_by_interests"):
        intro = "Here are the alumni whose experience best matches your goals:"
    else:
        intro = "Here are some alumni you could talk to (add your target roles to your profile for closer matches):"
    lines = [intro, "", *(_line(p) for p in people), ""]
    if result.get("can_send_requests"):
        lines.append("Open one in Alumni Match to send a request with a short note. If they accept, you'll see "
                     "the contact details they choose to share.")
    else:
        lines.append("To send a request, first turn on Alumni matching under Settings → Privacy; then open Alumni "
                     "Match to contact them.")
    card = {
        "kind": "alumni_matches",
        "can_send_requests": bool(result.get("can_send_requests")),
        "items": [
            {
                "id": p["id"], "name": p["name"], "position": p["position"], "company": p["company"],
                "class_year": p.get("class_year"), "expertise": [e["label"] for e in p["expertise"]],
                "matched": p.get("matched", []), "request_status": (p.get("request") or {}).get("status"),
            }
            for p in people
        ],
    }
    return ToolAnswer(text="\n".join(lines), agent_used="alumni_agent", card=card)


def _handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    wanted = state.alumni_role_hint
    result = alumni.list_matches(state.user_id, expertise=[wanted] if wanted else None)
    filtered = bool(wanted and result["items"])
    if wanted and not result["items"]:
        result = alumni.list_matches(state.user_id)
    labels = {o["tag"]: o["label"] for o in result.get("expertise_options", [])}
    return build_answer(result, wanted, labels.get(wanted, wanted), filtered)


def _fallback(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
    return ToolAnswer(text="I couldn't load the alumni directory right now. Please open Alumni Match from the "
                           "sidebar, or try again shortly.", agent_used="alumni_agent_fallback")


ALUMNI_MATCH_TOOL = Tool(
    name="alumni",
    description="Alumni Match — the student's best-matching listed alumni, with links to contact them.",
    input_model=ChatToolInput,
    handler=_handler,
    fallback=_fallback,
    trigger_intents=frozenset({"alumni"}),
    skip_evaluation=True,
)
