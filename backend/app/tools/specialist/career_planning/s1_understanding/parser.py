"""
S1 — reads a career message into a ParsedCareerRequest with one small
model call (JSON out), run alongside S2's data gathering.

The mode comes from the intent classifier (TurnState.career_mode_hint);
this step maps the roles the message names onto the knowledge base's role
families — "quant researcher" is quantitative_finance, "compliance
officer" regulation_governance — which plain text matching can't, and
picks up situation facts stated in passing. When the previous reply
asked the student to choose a role, its options are passed in too, so
"the second one" or "SE" resolves to a role. The role catalogue is passed
in (tag, name, definition), so the parser itself reads no data. Any
failure yields an empty request marked parse_failed: the answer still
runs, on the profile alone.
"""

from __future__ import annotations

import json

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.tools.specialist.career_planning.s1_understanding.schema import (
    INTERNSHIP_STATUSES,
    JOB_SEARCH_TIMELINES,
    MARKETS,
    ParsedCareerRequest,
)

logger = get_logger(__name__)

_MAX_TOKENS = 300

_PROMPT = """\
You read one message from a student or applicant of the NUS MSc Digital \
Financial Technology asking for career advice, and extract what it says. \
Extract only what the message actually says — never guess; use an empty \
list or null for anything it doesn't mention.

The programme's role families (tag: name — definition):
{roles}

Reply with ONLY a JSON object with these keys:
- "roles": the tags of the role families the message names or describes, \
in any language, in the order named — "数据工程" is data_engineering — and \
map job titles onto the closest family (e.g. "quant \
researcher" -> quantitative_finance, "compliance officer" -> \
regulation_governance, "data scientist" -> data_analytics or \
machine_learning_ai by what they describe). Only tags from the list above.
- "unmatched_roles": job titles or fields the message names that fit none \
of the families, verbatim.
- "job_search_timeline": when they plan to look for work, one of \
{timelines}, else null.
- "internship_status": their internship situation, one of {statuses}, else null.
- "target_markets": where they want to work, from {markets} (SG Singapore, \
CN mainland China, IN India, HK Hong Kong, SEA_OTHER other Southeast Asia, \
US, EUROPE, OTHER, ANY anywhere).
"""


def _catalogue(role_catalog: list[dict]) -> str:
    def line(r: dict) -> str:
        names = " / ".join(n for n in (r["name"], r.get("name_zh")) if n)
        definition = r.get("definition") or ""
        return f"- {r['tag']}: {names}" + (f" — {definition}" if definition else "")
    return "\n".join(line(r) for r in role_catalog)


_OPTIONS = """

The assistant's previous reply asked the student to choose one of these \
roles, in this order:
{options}
If the message picks one — by name, by position ("the second one"), by an \
abbreviation or by describing it — put its tag in "roles"."""


def parse(message: str, role_catalog: list[dict], options: list[dict] | None = None) -> ParsedCareerRequest:
    """`role_catalog`: [{tag, name, definition}]; `options`: the roles the
    previous reply offered, [{key, label}], if it asked for a choice."""
    if not message.strip():
        return ParsedCareerRequest()
    prompt = _PROMPT.format(
        roles=_catalogue(role_catalog),
        timelines=", ".join(JOB_SEARCH_TIMELINES),
        statuses=", ".join(INTERNSHIP_STATUSES),
        markets=", ".join(MARKETS),
    )
    if options:
        listed = "\n".join(f"{i}. {o['label']} ({o['key']})" for i, o in enumerate(options, start=1))
        prompt += _OPTIONS.format(options=listed)
    try:
        raw = json.loads(llm.complete(prompt, message, temperature=0, max_tokens=_MAX_TOKENS).strip())
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        parsed = ParsedCareerRequest.model_validate(raw)
    except Exception:
        logger.exception("career planning: parsing the request failed, using the profile alone")
        return ParsedCareerRequest(parse_failed=True)
    known = {r["tag"] for r in role_catalog}
    return parsed.model_copy(update={"roles": [r for r in parsed.roles if r in known]})
