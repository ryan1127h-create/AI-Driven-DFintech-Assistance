"""Natural-language -> JSON draft via DeepSeek. The ONLY LLM-dependent step.

Takes the current file content plus a plain-language instruction and returns a
complete updated JSON object. Requires DEEPSEEK_API_KEY; raises a clear error
otherwise (authoring cannot proceed without it).
"""
from __future__ import annotations

import json

from common import config

from .registry import EditableTarget

_SYSTEM = (
    "You edit a JSON configuration file for a university assistant. You will be "
    "given the file's purpose, its CURRENT content, and a plain-language "
    "instruction. Apply ONLY the requested change. Return the COMPLETE updated "
    "JSON object and nothing else. Keep every other field unchanged, including "
    "any '_comment'. Do not add or remove top-level keys. Output valid JSON only."
)


class ExtractionError(RuntimeError):
    pass


def _client():
    if not config.is_configured():
        raise ExtractionError(
            "DeepSeek API key is not configured. Add it on the /settings page, or set environment variable "
            "DEEPSEEK_API_KEY。"
        )
    from openai import OpenAI

    return OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())


def extract(target: EditableTarget, current: dict, instruction: str) -> dict:
    """Return a complete updated JSON draft. Raises ExtractionError on failure."""
    model = config.get_model()
    client = _client()
    user = (
        f"File purpose: {target.description}\n"
        f"Editable section key: '{target.edit_key}'\n\n"
        f"CURRENT content:\n{json.dumps(current, ensure_ascii=False, indent=2)}\n\n"
        f"Instruction: {instruction}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
    except Exception as e:
        raise ExtractionError(f"DeepSeek call failed: {e}") from e

    if not content:
        raise ExtractionError("DeepSeek returned empty content")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"DeepSeek did not return valid JSON: {e}") from e
