"""
S1 — reads what an assessment message says about the applicant ("I studied
economics, IELTS 6.5, no coding") into profile field values, with one
small model call (JSON out), run alongside S2's data gathering.

Only what the message states explicitly is kept, and every value is
checked against the field's allowed values here — one bad value drops
that field, never the rest. A numeric GPA is never turned into a band:
scales differ between universities, so only a class or band the message
names counts. Any failure gives empty facts marked parse_failed; the
assessment still runs, on the profile alone.
"""

from __future__ import annotations

import json
import re
from datetime import date

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger
from app.tools.specialist.assessment.s1_understanding.schema import (
    LEVELS,
    MULTI_CHOICES,
    SINGLE_CHOICES,
    TEST_KEYS,
    StatedFacts,
)

logger = get_logger(__name__)

_MAX_TOKENS = 500

_PROMPT = """\
You read one message from someone asking whether they are ready to apply to \
the NUS MSc Digital Financial Technology, and extract what it says about \
them. Extract ONLY what the message states explicitly — never guess, infer \
or assume; leave out every key the message doesn't settle.

Reply with ONLY a JSON object using these keys, each optional:
- "highest_degree": one of {highest_degree} — only when they name the level (bachelor's, master's, PhD).
- "degree_discipline_category": their degree's discipline, one of \
{degree_discipline_category} (cs_se computer science / software engineering; \
information_systems; engineering; math_stats_physics maths / statistics / \
physics; finance_econ_accounting finance / economics / accounting; \
business_mgmt business / management; other_social_science; humanities_other).
- "bachelor_grad_year": the year they finished (or will finish) their bachelor's, as a number.
- "gpa_band": only when the message names a class or ranking — one of \
{gpa_band} (first class -> first_class_equiv, second upper -> \
second_upper_equiv, top 10% -> top_10pct). Never convert a numeric GPA.
- "english_medium_degree": true / false, only when they say whether their \
degree was taught in English.
- "admission_tests": a list of {{"key": one of {tests}, "score": number, \
"test_date": "YYYY-MM-DD", "YYYY-MM" or null}} for scores they state (雅思 is IELTS, 托福 is TOEFL).
- "code_level": programming, 0-4 (0 never written code, 1 can adapt \
tutorial code, 2 has written data-processing scripts independently, 3 has \
built a complete project with tests, 4 uses it regularly at work) — "no \
coding" is 0.
- "math_stats_level": 1-3, "finance_level": 1-3 — only if they describe it clearly.
- "tech_stack": from {tech_stack}.
- "prior_coursework": courses they have taken, from {prior_coursework}.
- "total_work_years": full-time work, one of {total_work_years}.
- "function_experience": kinds of work done, from {function_experience}.
- "research_output": one of {research_output}.
- "certifications": from {certifications}.
"""


def _prompt() -> str:
    choices = {**SINGLE_CHOICES, **MULTI_CHOICES}
    return _PROMPT.format(tests=", ".join(TEST_KEYS), **{k: ", ".join(v) for k, v in choices.items()})


def _test(item) -> dict | None:
    if not isinstance(item, dict) or item.get("key") not in TEST_KEYS:
        return None
    try:
        score = float(item["score"])
    except (KeyError, TypeError, ValueError):
        return None
    test = {"key": item["key"], "score": score}
    when = str(item.get("test_date") or "")
    if len(when) == 7:  # a month only ("2025-06"): its first day
        when += "-01"
    try:
        test["test_date"] = date.fromisoformat(when).isoformat() if when else None
    except ValueError:
        test["test_date"] = None
    return test


def clean(raw: dict) -> dict:
    """The values that fit their field; anything else is dropped."""
    values: dict = {}
    for key, allowed in SINGLE_CHOICES.items():
        if raw.get(key) in allowed:
            values[key] = raw[key]
    for key, allowed in MULTI_CHOICES.items():
        items = [v for v in raw.get(key) or [] if v in allowed] if isinstance(raw.get(key), list) else []
        if items:
            values[key] = list(dict.fromkeys(items))
    for key, (low, high) in LEVELS.items():
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
            values[key] = value
    if isinstance(raw.get("english_medium_degree"), bool):
        values["english_medium_degree"] = raw["english_medium_degree"]
    year = raw.get("bachelor_grad_year")
    if isinstance(year, int) and 1950 <= year <= date.today().year + 6:
        values["bachelor_grad_year"] = year
    tests = [t for t in (_test(i) for i in raw.get("admission_tests") or []) if t] \
        if isinstance(raw.get("admission_tests"), list) else []
    if tests:
        values["admission_tests"] = tests
    return values


# Words that name a degree level; without one, a level the model returns
# was inferred ("I studied economics"), not stated.
_DEGREE_LEVEL = re.compile(r"bachelor|undergrad|master|msc|mba|ph\.?d|doctor|本科|学士|硕士|研究生|博士",
                           re.IGNORECASE)


def parse(message: str) -> StatedFacts:
    if not message.strip():
        return StatedFacts()
    try:
        raw = json.loads(llm.complete(_prompt(), message, temperature=0, max_tokens=_MAX_TOKENS).strip()
                         .removeprefix("```json").removeprefix("```").removesuffix("```"))
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
    except Exception:
        logger.exception("assessment: parsing the message failed, using the profile alone")
        return StatedFacts(parse_failed=True)
    values = clean(raw)
    if "highest_degree" in values and not _DEGREE_LEVEL.search(message):
        del values["highest_degree"]
    return StatedFacts(values=values)
