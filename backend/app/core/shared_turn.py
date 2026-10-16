"""
A multi-tool turn: one message answered by several tools in parallel,
whose replies are joined as they are (orchestrator/dispatch/merge.py).
Each tool writes from the whole message, so each is told which other tools
cover which parts — to answer only its own, and not to mention the rest.
"""

from __future__ import annotations

# Tool name -> what it covers, in words.
TOOL_TOPICS = {
    "admissions": "admissions and applying",
    "academic": "courses and the curriculum",
    "financial": "fees and funding",
    "faq": "general programme questions",
    "course_recommendation": "personal course recommendations",
    "career": "career planning",
    "comparison": "comparisons with other programmes",
    "assessment": "the applicant's profile assessment",
}


def instruction(other_tools: tuple[str, ...] | list[str]) -> str:
    """The line for a generation prompt; empty when the tool answers alone."""
    if not other_tools:
        return ""
    others = ", ".join(TOOL_TOPICS.get(t, t.replace("_", " ")) for t in other_tools)
    return (f"Shared message: the user's message also asks about {others}, and separate answers on "
            "that are shown right after yours. Answer only your own part, written as if the user had "
            "asked only about it: no word about the other parts — not even that they are handled "
            "elsewhere — and no reference to other answers or advisors.")


def with_instruction(prompt: str, other_tools: tuple[str, ...] | list[str]) -> str:
    line = instruction(other_tools)
    return f"{prompt.rstrip()}\n\n{line}\n" if line else prompt
