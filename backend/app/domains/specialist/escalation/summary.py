"""
The case summary staff read first: two or three sentences on what the user
needs, written by the LLM from the last few messages of the conversation.
Never fails: without a usable answer it falls back to the user's own words.
"""

from __future__ import annotations

from app.adapters.deepseek_adapter import llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_SUMMARY_CHARS = 600
_FALLBACK_CHARS = 400

_PROMPT = """\
You write the summary of a support case for staff of the NUS MSc Digital \
Financial Technology programme office. A student or applicant was talking \
to the programme's AI assistant and the conversation was escalated to a \
human ({category}).

The case is about the MESSAGE THAT RAISED THE CASE below. Write 2-3 plain \
sentences, in English, for the staff member who will pick it up: what the \
person needs in that message, any facts they gave (dates, courses, \
application, amounts), and what they want staff to do. Use the EARLIER \
CONVERSATION only to make that message understandable — never summarise an \
earlier request instead, and leave out what the assistant said unless the \
message refers to it. Do not add advice, do not address the person, do not \
invent anything. Output only the summary."""

_CATEGORY_NAMES = {
    "explicit_request": "the user asked to speak to a staff member",
    "complaint": "the user made a complaint",
    "policy_exception": "the user asked for a policy exception",
    "sensitive": "the user raised a sensitive personal situation",
    "low_confidence": "the assistant could not answer reliably",
}


def summarize(transcript: list[tuple[str, str]], category: str) -> str:
    """`transcript`: [(role, text)] oldest first, the user's latest message
    last."""
    trigger_at = next((i for i in range(len(transcript) - 1, -1, -1) if transcript[i][0] == "user"), None)
    latest_user = transcript[trigger_at][1] if trigger_at is not None else ""
    fallback = latest_user.strip()[:_FALLBACK_CHARS] or "Escalated from the chat assistant."
    earlier = transcript[:trigger_at] if trigger_at is not None else transcript
    lines = "\n".join(f"{'User' if role == 'user' else 'Assistant'}: {text.strip()[:800]}" for role, text in earlier)
    prompt_input = (f"EARLIER CONVERSATION (context only):\n{lines or '(none)'}\n\n"
                    f"MESSAGE THAT RAISED THE CASE:\nUser: {latest_user.strip()[:1200]}")
    try:
        summary = llm.complete(
            _PROMPT.format(category=_CATEGORY_NAMES.get(category, category)), prompt_input,
            temperature=0, max_tokens=300,
        ).strip()
    except Exception:
        logger.exception("summarising a %s case failed, using the user's message", category)
        return fallback
    return summary[:_MAX_SUMMARY_CHARS] if summary else fallback
