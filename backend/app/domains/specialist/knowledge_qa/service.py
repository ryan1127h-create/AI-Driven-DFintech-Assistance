"""
Fixed-topic registry for Knowledge QA: one role prompt + soft topic-boost
per topic (retrieval_scope() tells the caller how to retrieve), plus the
generic escape hatch (answer_with_role_prompt) for a caller with its own
role prompt — currently used by program_comparison's legacy-RAG fallback
(see app/tools/specialist/program_comparison_tool.py). The caller
retrieves and passes the context in.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.specialist.knowledge_qa import qa_agent
from app.domains.specialist.knowledge_qa.qa_agent import OnEvent


@dataclass(frozen=True)
class _TopicSpec:
    role_prompt: str
    boost_topics: set[str]


_TOPICS: dict[str, _TopicSpec] = {
    "admissions": _TopicSpec(
        role_prompt="""\
You are the Admissions Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers:
- Academic admission requirements (bachelor's degree, STEM / Finance / Economics \
backgrounds)
- Work experience and programming proficiency expectations
- Standardised test guidelines (GRE, GMAT) and English proficiency requirements \
(TOEFL, IELTS)
- Application method, application fee, opening and closing dates, and outcome timelines
- The NUS Graduate Admission System

Official information sources (cite when helpful):
{official_sources}
""",
        boost_topics={"admissions"},
    ),
    "academic": _TopicSpec(
        role_prompt="""\
You are the Academic Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers:
- Programme structure: total units (52), core courses, elective courses, and \
the FT5007 Capstone Project
- Individual course descriptions, semester availability, prerequisites, and \
preclusions
- The three elective tracks: Computing Technologies; Financial Data Analytics \
and Intelligence; Digital Financial Transactions and Risk Management
- Suggested full-time (1.5-year) and part-time (2.5-year) course plans
- Graduation requirements (minimum GPA 3.0, all programme requirements fulfilled)
- Core course replacement and waiver options
- Workload limits per semester for full-time and part-time students

Official information source (cite when helpful):
- NUS MSc DFinTech Programme Information: https://www.comp.nus.edu.sg/programmes/pg/mdft/
- Live course availability: https://nusmods.com
""",
        boost_topics={"academic"},
    ),
    "financial": _TopicSpec(
        role_prompt="""\
You are the Financial Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers:
- Tuition fees (S$74,120 for up to 52 units) and the acceptance fee (S$7,412)
- NUS Master's Degree by Coursework Enhanced Tuition Fee Rebate: eligibility \
(Singapore Citizens and PRs only), rebate amount (40%), and key conditions
- Singapore Digital (SG Digital) Scholarship: coverage, eligibility, bond \
obligations, and study tracks
- NUS GRTII Master's Scholarship: amount (S$45,000 lump sum), eligibility, \
bond obligations, disbursement process, and application steps
- General guidance on comparing financial options and where to seek further help

Official information source (cite when helpful):
- NUS MSc DFinTech Fees and Scholarships: https://www.comp.nus.edu.sg/programmes/pg/mdft/scholarships/
""",
        boost_topics={"financial"},
    ),
    "faq": _TopicSpec(
        role_prompt="""\
You are the General Programme Assistant for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your expertise covers general programme information that doesn't fit a more \
specific category — student life, frequently asked questions, and other \
miscellaneous programme details.

If a question turns out to be specifically about admissions requirements, \
tuition/scholarships, course curriculum, career pathways, or comparisons with \
other universities, answer it if the reference material covers it, but keep in \
mind a more specialised advisor may give a more complete answer.
""",
        boost_topics={"faq"},
    ),
}


def retrieval_scope(topic: str) -> set[str]:
    """The topics to boost when retrieving context for this fixed topic."""
    return set(_TOPICS[topic].boost_topics)


def answer_topic(
    topic: str, user_message: str, chat_history: list[dict],
    *, context: str | None, official_sources: str, on_event: OnEvent | None = None,
    depth: str | None = None,
) -> str:
    """Answers for one of the four fixed topics above from the caller's
    retrieved `context`; `official_sources` fills the admissions prompt's
    source list."""
    role_prompt = _TOPICS[topic].role_prompt.replace("{official_sources}", official_sources)
    return qa_agent.answer(role_prompt, user_message, chat_history, context=context, on_event=on_event, depth=depth)


def answer_with_role_prompt(
    role_prompt: str, user_message: str, chat_history: list[dict],
    *, context: str | None, on_event: OnEvent | None = None, depth: str | None = None,
) -> str:
    """Generic escape hatch for a caller with its own role prompt, outside
    the four fixed topics above."""
    return qa_agent.answer(role_prompt, user_message, chat_history, context=context, on_event=on_event, depth=depth)
