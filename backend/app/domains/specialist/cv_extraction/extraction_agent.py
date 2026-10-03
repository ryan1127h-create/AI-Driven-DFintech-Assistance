"""
The extraction prompt and its one LLM call. The fields, and the values
each accepts, come from the profile field dictionary the caller passes in,
so the prompt always matches what the profile will accept.
"""

from __future__ import annotations

import json

from app.adapters.deepseek_adapter import llm

# Long enough for a multi-page CV; anything past it is almost always
# references or publication lists, which none of the fields need.
MAX_CV_CHARS = 20000

_PROMPT_HEAD = """\
You read a CV for the NUS MSc Digital Financial Technology programme's \
student assistant and fill in profile fields from it. Return ONLY a JSON \
object, no markdown. For every field below that the CV states explicitly, \
include

  "<field_key>": {"value": <value>, "quote": "<the shortest exact span copied from the CV that states it>"}

Rules:
- Only what the CV says explicitly. Never guess, infer, estimate, or fill \
a field from what is typical. Leave a field out when unsure.
- Never record an absence: when the CV doesn't mention something (research, \
certifications, ...), leave that field out instead of answering "none".
- The quote must be copied character for character from the CV text, \
at most 200 characters.
- Use only the listed option keys as values (the part before the colon), \
never the labels. A list field's value is a JSON array of keys.
- Structured items follow the format given for the field.

Fields:
"""


def _describe(definition: dict) -> str:
    line = f'- {definition["field_key"]} ({definition["value_type"]}): {definition["label"]}'
    labels = definition.get("value_labels") or {}
    options = definition.get("allowed_values")
    if options:
        line += "; options: " + ", ".join(
            f"{o}: {labels[str(o)]}" if str(o) in labels else str(o) for o in options
        )
    if definition.get("max_items"):
        line += f"; at most {definition['max_items']} items"
    if definition.get("value_spec"):
        line += f"; format: {definition['value_spec']}"
    return line


def build_prompt(targets: list[dict]) -> str:
    return _PROMPT_HEAD + "\n".join(_describe(d) for d in targets)


def extract(cv_text: str, targets: list[dict]) -> dict:
    """field_key -> {"value", "quote"} as the model returned it (unchecked).
    Raises ValueError when the reply isn't a JSON object."""
    reply = llm.complete(build_prompt(targets), cv_text[:MAX_CV_CHARS], temperature=0, max_tokens=3000)
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"expected a JSON object, got {type(result).__name__}")
    return result
