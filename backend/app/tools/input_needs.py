"""
Helpers for a tool's input_needs (see app/tools/contracts.py): turning
"this profile field is missing" into the right MissingInputField, with the
consent the profile needs taken into account.

A profile field a tool reads for a purpose is invisible without that
purpose's consent (profile.purpose_consents), even when it's filled in.
Asking for it then would loop — the user fills it in, the tool still can't
see it, asks again — so without the consent:
  - a required field becomes a request to turn the consent on;
  - an optional or supplementary one isn't asked for at all: the answer
    goes ahead unpersonalised, and says so.
"""

from __future__ import annotations

from app.domains.profile.interface import missing_purpose_consent
from app.tools.contracts import InputLevel, MissingInputField
from app.tools.turn_context import TurnState

CONSENT_PROMPT = (
    "To use your profile for this, personalised recommendations need to be "
    "turned on. Turn them on to continue."
)


def profile_field_need(
    state: TurnState,
    purpose: str,
    facts: dict,
    field_key: str,
    level: InputLevel,
    prompt: str,
) -> MissingInputField | None:
    """What to ask for when `field_key` may be missing for `purpose`;
    None when nothing should be asked. `facts` is the purpose's profile
    facts as the tool reads them."""
    if not state.user_id or facts.get(field_key) not in (None, "", []):
        return None
    consent = missing_purpose_consent(state.user_id, purpose)
    if consent:
        if level != "required":
            return None
        return MissingInputField(
            slot=f"consent:{consent}", prompt=CONSENT_PROMPT, level="required", consent_key=consent,
        )
    return MissingInputField(slot=field_key, prompt=prompt, field_key=field_key, level=level)
