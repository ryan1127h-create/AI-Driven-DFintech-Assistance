"""
Shared rendering layer: turns a specialist's render view (a structured
dict its S7 payload builds — course recommendation's, career planning's,
programme comparison's)
into one natural-language chat reply, streamed.

The view already holds every fact, figure and judgement; this step only
connects them into one coherent reply in the reply language (see
app/core/reply_language.py) under the caller's style prompt — it composes no new analysis. The callers
check the reply against the view themselves (their guardrail.py) and fall
back to render_template(), the deterministic walk of the view this module
also provides.
"""

from __future__ import annotations

from app.adapters.deepseek_adapter import llm
from app.core import answer_depth, reply_language
from app.core.logging import get_logger
from app.tools.contracts import OnEvent

logger = get_logger(__name__)

# Headroom above the reply, as a safety margin against truncation: a rich
# view (a three-programme comparison with a table) is genuinely long, and
# 2200 proved too tight in testing.
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


def render_template(result: dict) -> str:
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
    on_event: OnEvent | None = None, depth: str | None = None, language: str | None = None,
) -> tuple[str, list[str]]:
    """
    Renders a specialist's render view into one
    chat reply. Never raises — any failure falls back to
    render_template(). `language` is the reply language (an ISO code;
    None follows the user's message). Returns (reply_text, sources) where
    `sources` is result.get("sources", []) verbatim.
    """
    sources = list(result.get("sources") or [])
    draft = _render_draft_block(result)

    try:
        prompt = reply_language.with_instruction(
            answer_depth.with_instruction(_RENDER_PROMPT.format(style_prompt=style_prompt, draft=draft), depth),
            language,
        )
        chunks: list[str] = []
        for chunk in llm.stream(prompt, [{"role": "user", "content": user_message}], temperature=0.2, max_tokens=answer_depth.max_tokens(depth, _MAX_TOKENS)):
            chunks.append(chunk)
            if on_event is not None:
                on_event({"type": "token", "text": chunk})
        reply = "".join(chunks).strip()
        if reply:
            return reply, sources
    except Exception:
        logger.exception("structured reply: the render call failed, using the template")

    return render_template(result), sources
