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


# Who answers a point both parts could claim, by the other tool present:
# without it, two answers each take the point and contradict each other
# (fees answering "how do the fees compare with HKU?" from MSc DFT material
# alone, next to the comparison that has HKU's figures).
_OWNERSHIP = {
    "comparison": "anything about another programme — its fees, funding, entry requirements, deadlines, "
                  "length or outcomes — is covered by the comparison, not by you",
    "financial": "fee amounts (tuition, application and acceptance fees), rebates, scholarships and other "
                 "funding are covered by the fees answer; at most name a fee as a step, without its amount",
    "admissions": "how to apply, application status, accepting an offer and the Student's Pass are covered "
                  "by the admissions answer",
    "career": "the user's own career fit and readiness are covered by the career answer",
    "course_recommendation": "which courses the user should take are covered by the course recommendation",
}


def instruction(other_tools: tuple[str, ...] | list[str]) -> str:
    """The line for a generation prompt; empty when the tool answers alone."""
    if not other_tools:
        return ""
    others = ", ".join(TOOL_TOPICS.get(t, t.replace("_", " ")) for t in other_tools)
    line = (f"Shared message: the user's message also asks about {others}, and separate answers on "
            "that are shown right after yours. Answer only your own part, written as if the user had "
            "asked only about it: no word about the other parts — not even that they are handled "
            "elsewhere — and no reference to other answers or advisors.")
    owned = [_OWNERSHIP[t] for t in other_tools if t in _OWNERSHIP]
    if owned:
        line += (" Where your part and theirs overlap, leave the shared point to them: " + "; ".join(owned)
                 + ". Such a point is not a gap in your material: never say you can't cover it, that your "
                 "sources lack it, or that it is answered separately — just leave it out.")
    return line


def with_instruction(prompt: str, other_tools: tuple[str, ...] | list[str]) -> str:
    line = instruction(other_tools)
    return f"{prompt.rstrip()}\n\n{line}\n" if line else prompt
