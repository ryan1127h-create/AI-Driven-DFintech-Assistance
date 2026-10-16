"""
Knowledge QA for the four fixed topics (admissions, academic, financial,
faq): one advisor prompt with a per-topic focus, a soft retrieval boost
per topic (retrieval_scope() tells the caller how to retrieve), and a
check of the answer's figures.

No programme fact is written into the prompts: every figure comes from
what the caller passes in — the current facts block (facts.py) and the
retrieved reference material — so a new intake's fees or dates only need
the catalogue and the knowledge base updated.

An answer is streamed, then checked (guardrail.py). One that cites a
figure or date neither source holds is generated once more, silently,
with the problem spelled out; if that still fails, a reply that points to
the official pages replaces it. The client swaps the streamed draft for
the final text.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domains.specialist.knowledge_qa import guardrail, qa_agent
from app.domains.specialist.knowledge_qa.facts import ENQUIRY_URL
from app.domains.specialist.knowledge_qa.qa_agent import OnEvent

logger = get_logger(__name__)

_ADVISOR = """\
You are the {role} for the NUS Master of Science in Digital Financial Technology \
(MSc DFT, also written MSc DFinTech) programme.

Your focus:
{focus}"""


@dataclass(frozen=True)
class _TopicSpec:
    role: str
    focus: str
    boost_topics: frozenset[str]


_TOPICS: dict[str, _TopicSpec] = {
    "admissions": _TopicSpec(
        "Admissions Advisor",
        "- Who can apply: degree background, programming and quantitative preparation, work experience\n"
        "- Test scores: GRE/GMAT, TOEFL/IELTS\n"
        "- How and when to apply: the application portal, documents, application fee, opening and "
        "closing dates, outcome timing, offer acceptance",
        frozenset({"admissions"}),
    ),
    "academic": _TopicSpec(
        "Academic Advisor",
        "- Programme structure: units, core and elective courses, the capstone project or internship\n"
        "- Individual courses: content, prerequisites, preclusions, when they run (nusmods.com has live "
        "availability)\n"
        "- Course plans for full-time and part-time study, workload limits, continuation and "
        "graduation requirements, course replacement and waivers",
        frozenset({"academic"}),
    ),
    "financial": _TopicSpec(
        "Financial Advisor",
        "- Tuition and other fees, and how they are paid\n"
        "- Tuition fee rebates and scholarships: who qualifies, amounts, bonds, how to apply\n"
        "- Where to find further financial help",
        frozenset({"financial"}),
    ),
    "faq": _TopicSpec(
        "General Programme Assistant",
        "- General programme questions that fit no narrower topic: student life, visas and "
        "accommodation, part-time work, and other practical matters\n"
        "- If a question is really about admissions, fees, courses or careers, answer it from the "
        "material all the same",
        frozenset({"faq"}),
    ),
}

_CORRECTION = """

A previous draft of this answer was rejected: {problems}. Use only the figures and \
dates that appear in the CURRENT PROGRAMME FACTS or the REFERENCE MATERIAL, exactly as \
written, or one-step calculations on them with the working shown (both figures and \
the result); leave out anything else."""

_UNVERIFIED_REPLY = (
    "I couldn't confirm every detail of this answer against the official programme information, "
    "so rather than risk giving you a wrong figure, please check the official pages:\n\n"
    "- Programme website: {official_url}\n"
    "- Enquiries: {enquiry_url}"
)

_OFFICIAL_URL = "https://www.comp.nus.edu.sg/programmes/pg/mdft/"


def retrieval_scope(topic: str) -> set[str]:
    """The topics to boost when retrieving context for this fixed topic."""
    return set(_TOPICS[topic].boost_topics)


def answer_topic(
    topic: str, user_message: str, chat_history: list[dict],
    *, context: str | None, facts: str | None = None, on_event: OnEvent | None = None,
    depth: str | None = None, language: str | None = None,
) -> str:
    """Answers for one of the four fixed topics from the current `facts`
    block and the retrieved `context` (either may be None)."""
    if not user_message:
        return "I couldn't identify your question. Could you please rephrase it?"
    spec = _TOPICS[topic]
    role_prompt = _ADVISOR.format(role=spec.role, focus=spec.focus)
    sources = f"{facts or ''}\n{context or ''}"

    reply = qa_agent.answer(role_prompt, user_message, chat_history,
                            context=context, facts=facts, on_event=on_event, depth=depth, language=language)
    problems = guardrail.check(reply, sources, user_message)
    if not problems:
        return reply

    logger.warning("knowledge qa (%s) answer failed the check, regenerating: %s", topic, problems)
    reply = qa_agent.answer(role_prompt + _CORRECTION.format(problems="; ".join(problems)), user_message,
                            chat_history, context=context, facts=facts, on_event=None, depth=depth,
                            language=language)
    problems = guardrail.check(reply, sources, user_message)
    if not problems:
        return reply

    logger.warning("knowledge qa (%s) answer failed the check twice, pointing to the official pages: %s",
                   topic, problems)
    return _UNVERIFIED_REPLY.format(official_url=_OFFICIAL_URL, enquiry_url=ENQUIRY_URL)
