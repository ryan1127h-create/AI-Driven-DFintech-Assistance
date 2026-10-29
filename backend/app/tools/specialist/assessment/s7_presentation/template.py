"""
S7 — the assessment as a plain reply, written straight from the render view
(payload.py) with no LLM: used when a rendered reply fails the guardrail
twice. Says the same things the style prompt asks for, in the same order,
and nothing that isn't in the view.
"""

from __future__ import annotations

# payload.HARD_STATUS labels.
_STATUS_MARKS = {"met": "✓", "not needed": "✓", "gap": "✗", "to confirm": "?"}


def _line(item: dict, first: str) -> str:
    parts = [f"**{item[first]}**"]
    if item.get("status"):
        parts.append(f"{_STATUS_MARKS.get(item['status'], '')} {item['status']}".strip())
    text = " — ".join(parts)
    if item.get("finding"):
        text += f": {item['finding']}"
    return f"- {text}"


def render(view: dict) -> str:
    lines = [view["verdict"]["summary"]]
    if view.get("based_on"):
        lines[0] += f" (based on {view['based_on']})"

    if view.get("hard_conditions"):
        lines += ["", "**Entry requirements**"]
        for c in view["hard_conditions"]:
            lines.append(_line(c, "condition"))
            if c.get("action"):
                lines.append(f"  - Next step: {c['action']}")

    if view.get("strengths"):
        lines += ["", "**What works in your favour**"]
        lines += [_line(s, "factor") for s in view["strengths"]]

    if view.get("worth_strengthening"):
        lines += ["", "**Worth strengthening**"]
        for s in view["worth_strengthening"]:
            lines.append(_line(s, "factor") + (" (optional)" if s.get("optional") else ""))
            if s.get("action"):
                lines.append(f"  - {s['action']}")

    if view.get("application_period"):
        lines += ["", f"Application period — {view['application_period']}."]
    if view.get("still_unknown"):
        lines += ["", "To make this more complete, tell me: " + "; ".join(view["still_unknown"])]
    for note in view.get("notes") or []:
        lines += ["", note]
    if view.get("disclaimer"):
        lines += ["", f"_{view['disclaimer']}_"]
    return "\n".join(lines)
