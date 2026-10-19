"""
When a chat turn needs a human staff member — pure rules, no data access.

Direct escalations come from what the user said (the intent classifier's
"escalation" signal); a chained one from how the turn went (the answering
specialist fell back to a canned reply or failed). A clear request — to
speak to a person, a complaint, a sensitive situation — opens a case at
once; a request for a policy exception, or an answer the assistant
couldn't stand behind, only offers one, and the user decides.
"""

from __future__ import annotations

from dataclasses import dataclass

# Opened without asking: the user has said plainly what they need.
OPEN_AT_ONCE = {"explicit_request", "complaint", "sensitive"}
# Offered: the user may only be asking about the rules, or the answer may
# still be good enough for them.
OFFER_FIRST = {"policy_exception", "low_confidence"}
# Turn outcomes (orchestrator/turn_metrics.py) that mean the assistant
# couldn't give a proper answer.
_WEAK_OUTCOMES = {"fallback", "error"}

# Display names for chat.cases.origin_specialist, the agent that handled the turn.
_ORIGIN_LABELS = {
    "admissions": "Admissions", "academic": "Academic", "financial": "Fees & Finance", "career": "Career Planning",
    "comparison": "Programme Comparison", "faq": "FAQ", "assessment": "Readiness Assessment",
    "course_recommendation": "Course Recommendation", "supervisor": "General Chat", "orchestrator": "Orchestrator",
}


@dataclass(frozen=True)
class Decision:
    action: str            # "open" | "offer"
    category: str          # a chat.cases category
    trigger_source: str    # "direct" | "chained"
    priority: str          # "normal" | "urgent"


def decide(signal: dict | None, outcome: str, intents: list[str]) -> Decision | None:
    """`signal`: the classifier's {"category", "urgent"} or None; `outcome`:
    the turn's outcome from read_agent_used(); `intents`: the classified
    intents. None when the turn needs no human."""
    if signal:
        category = signal["category"]
        priority = "urgent" if signal.get("urgent") or category == "sensitive" else "normal"
        action = "open" if category in OPEN_AT_ONCE else "offer"
        return Decision(action, category, "direct", priority)
    # An off-topic message has no specialist answer to fall short of.
    if outcome in _WEAK_OUTCOMES and intents != ["off_topic"]:
        return Decision("offer", "low_confidence", "chained", "normal")
    return None


def origin_label(agents: list[str]) -> str:
    """The specialist(s) that handled the turn, for staff: "Admissions",
    "Admissions + FAQ", or "Other"."""
    labels = [_ORIGIN_LABELS.get(a, a.replace("_", " ").title()) for a in agents if a != "orchestrator"]
    return " + ".join(labels) or "Other"
