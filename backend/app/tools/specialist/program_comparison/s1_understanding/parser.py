"""
S1 — reads a comparison message into a ParsedComparisonRequest with one
small model call (JSON out), run alongside S2's data gathering.

The model maps the names a message uses onto catalogue programmes —
"港科大" is HKUST's MSc FinTech, "南洋理工的金融科技" NTU's — which plain
text matching can't, using the catalogue's names and aliases passed in;
it also maps a role the applicant aims for onto a role family. When the
previous reply offered programmes to choose from, those options are
passed in so "the second one" resolves. The parser reads no data itself.
Any failure yields an empty request marked parse_failed: the answer
still runs, from the classifier's hints and the profile.
"""

from __future__ import annotations

import json

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.tools.specialist.program_comparison.s1_understanding.schema import (
    CATEGORIES,
    DIMENSIONS,
    STUDY_MODES,
    ParsedComparisonRequest,
)

logger = get_logger(__name__)

_MAX_TOKENS = 300

_PROMPT = """\
You read one message to the NUS MSc Digital Financial Technology (MSc DFT) \
assistant about comparing master's programmes, and extract what it says. \
Extract only what the message actually says — never guess; use an empty \
list or null for anything it doesn't mention.

Programmes in the comparison data (id: name — university; other names):
{programs}

Role families (tag: name):
{roles}

Reply with ONLY a JSON object with these keys:
- "mode": "compare" when it weighs MSc DFT against other programmes (or \
asks how they differ); "detail" when it asks about one programme's facts \
only (e.g. "what are NTU's fees?"); "explore" when it asks which \
programmes exist or fit some conditions without naming them; else null.
- "programs": the ids of the programmes the message names or clearly \
means, in any language or abbreviation, in the order named ("this \
programme" / "DFT" / "本项目" is {target}). A university named alone \
means its programme in the list when it has exactly one; if it has \
several, the one the message describes, else put the name in \
"unmatched_programs". Only ids from the list above.
- "unmatched_programs": programmes or universities named that aren't in \
the list, verbatim.
- "dimensions": the aspects asked about, from {dimensions} (cost: fees and \
net cost; duration: length and credits; curriculum: courses and skills; \
admission: entry requirements and tests; flexibility: part-time, intakes; \
funding: scholarships and rebates; deadlines: application dates; \
location: city, country). Empty when it asks generally.
- "countries": ISO 3166 alpha-2 codes of places it wants programmes in \
(e.g. "香港" -> "HK", "UK" -> "GB").
- "study_mode": one of {study_modes} if it asks for that, else null.
- "categories": kinds of programme it asks for, from {categories}.
- "role": the tag of the role family it says the applicant aims for, else null.
- "intake_year": the academic year it says they will start (e.g. "2028年 \
入学", "Fall 2028" -> 2028), else null.
- "asks_which_suits": true when it asks which programme suits them, fits \
them best, or which they should choose (e.g. "which is best for me?", \
"我该选哪个？", "哪个更适合我"); else false.
"""

_OPTIONS = """

The assistant's previous reply offered these programmes to choose from, in \
this order:
{options}
If the message picks any — by name, by position ("the second one") or by \
describing it — put their ids in "programs"."""


def _catalogue(programs: list[dict]) -> str:
    lines = []
    for p in programs:
        u = p["university"]
        names = ", ".join(dict.fromkeys([p["short_name"], *p.get("aliases", []), u["short_name"], *u.get("aliases", [])]))
        lines.append(f"- {p['program_id']}: {p['name']} — {u['name']} ({u['country_code']}); {names}")
    return "\n".join(lines)


def parse(message: str, programs: list[dict], role_catalog: list[dict],
          options: list[dict] | None = None) -> ParsedComparisonRequest:
    """`programs`: the catalogue (list_programs()); `role_catalog`: [{tag,
    name, name_zh}]; `options`: the programmes the previous reply offered,
    [{key, label}], if it asked for a choice."""
    if not message.strip():
        return ParsedComparisonRequest()
    target = next((p["program_id"] for p in programs if p["is_target"]), "")
    prompt = _PROMPT.format(
        programs=_catalogue(programs),
        roles="\n".join(f"- {r['tag']}: " + " / ".join(n for n in (r["name"], r.get("name_zh")) if n)
                        for r in role_catalog),
        target=target, dimensions=", ".join(DIMENSIONS), study_modes=", ".join(STUDY_MODES),
        categories=", ".join(CATEGORIES),
    )
    if options:
        listed = "\n".join(f"{i}. {o['label']} ({o['key']})" for i, o in enumerate(options, start=1))
        prompt += _OPTIONS.format(options=listed)
    try:
        raw = json.loads(llm.complete(prompt, message, temperature=0, max_tokens=_MAX_TOKENS).strip())
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        parsed = ParsedComparisonRequest.model_validate(raw)
    except Exception:
        logger.exception("programme comparison: parsing the request failed, using hints and the profile")
        return ParsedComparisonRequest(parse_failed=True)
    known_programs = {p["program_id"] for p in programs}
    known_roles = {r["tag"] for r in role_catalog}
    return parsed.model_copy(update={
        "programs": [p for p in parsed.programs if p in known_programs],
        "role": parsed.role if parsed.role in known_roles else None,
    })
