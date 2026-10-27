"""
Public interface of the escalation domain — the only module the
orchestrator imports from app.domains.specialist.escalation. It reads no
data: turn_service passes in the turn's signals and stores the case
through the conversation domain.

Usage:
    from app.domains.specialist.escalation import interface as escalation

    decision = escalation.decide(classified.escalation, outcome.outcome, intents)
"""

from __future__ import annotations

from app.domains.specialist.escalation.policy import OPEN_AT_ONCE, Decision, decide, origin_label
from app.domains.specialist.escalation.summary import summarize

__all__ = ["Decision", "HANDOFF_NOTE", "OPEN_AT_ONCE", "SUPPORT_RESOURCES", "decide", "origin_label", "summarize"]

# Given to the answering model when the user's message opens a case: the
# reply and the "passed to the programme office" card must agree.
HANDOFF_NOTE = (
    "This conversation is being passed to a staff member of the programme office, "
    "who will follow up with the user by email. Say so briefly and kindly in your reply. "
    "Still answer whatever part of the message you can, but do not ask the user for details "
    "the staff member will gather themselves, and do not promise outcomes or timelines."
)

# Shown with a sensitive case, straight away: staff reply later, these are
# for right now.
SUPPORT_RESOURCES = [
    {"label": "NUS University Counselling Services", "detail": "Confidential counselling for NUS students"},
    {"label": "Samaritans of Singapore (24 hours)", "detail": "Call 1767"},
    {"label": "Emergency in Singapore", "detail": "Call 995 (ambulance) or 999 (police)"},
]
