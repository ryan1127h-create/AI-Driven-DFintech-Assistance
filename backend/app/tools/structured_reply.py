"""
Shared rendering layer: turns a structured result dict from career_planning
or program_comparison (or any future domain with the same shape of
problem) into one natural-language chat reply.

Both source domains already write most of their content in natural
language (course-pick `reason`s, career_planning's `current_fit`/action
bullets, program_comparison's `best_fit_summary`/`program_comments`) —
they just return it as a structured dict shaped for a REST/frontend
consumer, not a single chat-ready string. So this is a *reflow* step, not
a "write from scratch" step: connect already-written material into one
coherent reply that matches the user's own language, not compose new
analysis. Kept deliberately cheap (small max_tokens) and with its own
deterministic fallback — mirrors the fallback discipline every LLM step
inside those two domains already follows.
"""

from __future__ import annotations

from app.adapters.deepseek_adapter import llm
from app.tools.contracts import OnEvent

# Headroom above the reflowed reply, as a safety margin against truncation.
# This step reflows existing prose rather than composing new analysis, so
# it needs less than the ~4000-12000 max_tokens the upstream domains' own
# generation steps use — but a rich result (e.g. a multi-programme
# comparison with per-programme match-score breakdowns) can still be
# genuinely long. 2200 proved too tight in testing (truncated a
# 2-programme comparison mid-sentence); 3500 leaves comfortable headroom.
_MAX_TOKENS = 3500

_RENDER_PROMPT = """\
{style_prompt}

Below is a structured result already computed for this user (course picks,
scores, action steps, comments — most of the text inside it was already
written by another step, you are not inventing new analysis). Your only job
is to weave it into ONE natural, coherent chat reply to the user's message.

Hard rules:
- Preserve every fact, figure, course code, score, and reason EXACTLY as
  given below — do not invent, drop, round, or "improve" anything.
- Reply in the same language the user's message was written in.
- Do not mention field names, JSON, "the data shows", or that this was
  assembled from a structured result — write as if you simply know this.
- If NOTES below contain a caveat (e.g. a role/programme could not be
  matched, or a fallback ranking was used), work it into the reply naturally
  as a short, honest caveat — do not omit it, and do not list it verbatim.
- Do not add a "Sources:" section yourself — the caller appends that
  separately.

Structured result:
{draft}
"""


def _format_value(value, indent: str = "") -> str:
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            rendered = _format_value(v, indent + "  ")
            lines.append(f"{indent}- {k}: {rendered}" if "\n" not in rendered else f"{indent}- {k}:\n{rendered}")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        if not value:
            return "(none)"
        lines = []
        for item in value:
            rendered = _format_value(item, indent + "  ")
            lines.append(f"{indent}- {rendered}" if "\n" not in rendered else f"{indent}-\n{rendered}")
        return "\n".join(lines)
    return str(value)


def _render_draft_block(result: dict) -> str:
    """Labels every top-level field except `sources` (appended separately by
    the caller, same convention as every RAG tool's "Sources:" footer) into
    a readable block for the LLM to reflow."""
    sections = []
    for key, value in result.items():
        if key == "sources":
            continue
        sections.append(f"[{key}]\n{_format_value(value)}")
    return "\n\n".join(sections)


def _template_fallback(result: dict) -> str:
    """Deterministic fallback used only if the render LLM call fails or
    returns something unusable — walks the structured result into a plain
    bulleted block. Less natural than the LLM path, but never invents or
    drops anything, and never raises."""
    lines = []
    for key, value in result.items():
        if key == "sources" or value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").capitalize()
        lines.append(f"{label}:")
        lines.append(_format_value(value, "  "))
    return "\n".join(lines) if lines else "No further details are available for this request."


def render_structured_reply(
    result: dict, user_message: str, style_prompt: str,
    on_event: OnEvent | None = None,
) -> tuple[str, list[str]]:
    """
    Renders a career_planning/program_comparison-shaped result dict into one
    chat reply. Never raises — any failure falls back to
    _template_fallback(). Returns (reply_text, sources) where `sources` is
    result.get("sources", []) verbatim.
    """
    sources = list(result.get("sources") or [])
    draft = _render_draft_block(result)

    try:
        prompt = _RENDER_PROMPT.format(style_prompt=style_prompt, draft=draft)
        chunks: list[str] = []
        for chunk in llm.stream(prompt, [{"role": "user", "content": user_message}], temperature=0.2, max_tokens=_MAX_TOKENS):
            chunks.append(chunk)
            if on_event is not None:
                on_event({"type": "token", "text": chunk})
        reply = "".join(chunks).strip()
        if reply:
            return reply, sources
    except Exception as exc:
        print(f"[structured_reply] Warning: render LLM call failed, using template fallback — {exc}")

    return _template_fallback(result), sources
