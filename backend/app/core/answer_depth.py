"""
The user's answer-detail preference (account settings: concise / standard /
detailed) as one line for a generation prompt and a token budget. Applied
where an answer is written — knowledge Q&A, the assessment, rendered
structured replies, general chat and multi-topic synthesis — never by
rewriting a finished answer, which would drop facts when shortening or
invent them when lengthening.
"""

from __future__ import annotations

DEPTHS = ("concise", "standard", "detailed")
DEFAULT_DEPTH = "standard"

_INSTRUCTIONS = {
    "concise": (
        "Answer length: this user prefers concise answers. Lead with the direct answer and keep to "
        "the essentials (roughly 120 words, or a short list); leave out background they didn't ask "
        "for. Every figure, date, condition and caveat you do include stays exact."
    ),
    "standard": "",
    "detailed": (
        "Answer length: this user prefers detailed answers. Give the fuller picture: the reasoning, "
        "relevant conditions and exceptions, and practical next steps, with headings or lists where "
        "they help. Add detail only from the material you were given; never invent it."
    ),
}
# Concise answers are kept short by the instruction, not by a budget that
# could cut one off mid-sentence; detailed ones get room to grow.
_TOKEN_SCALE = {"concise": 1.0, "standard": 1.0, "detailed": 1.5}


def normalize(depth: str | None) -> str:
    return depth if depth in DEPTHS else DEFAULT_DEPTH


def instruction(depth: str | None) -> str:
    """The line to add to a generation prompt; empty for "standard"."""
    return _INSTRUCTIONS[normalize(depth)]


def with_instruction(prompt: str, depth: str | None) -> str:
    line = instruction(depth)
    return f"{prompt.rstrip()}\n\n{line}\n" if line else prompt


def max_tokens(depth: str | None, base: int) -> int:
    return int(base * _TOKEN_SCALE[normalize(depth)])
