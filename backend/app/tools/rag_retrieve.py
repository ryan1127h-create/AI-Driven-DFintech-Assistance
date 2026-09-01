"""
RAG tool factory — builds registered Tools backed by the knowledge_retrieval
domain: retrieve (scoped by topic), build a tagged context, call the LLM.

Retrieval can optionally be scoped to knowledge_retrieval's topic buckets
(admissions/academic/financial/career/comparison/faq): filter_topics
hard-restricts candidates (only safe for topics with no overlap elsewhere,
e.g. career/comparison), boost_topics soft-boosts matching hits without
excluding anything else (safer default for topics whose boundaries aren't
clean). Leaving both unset falls back to plain unscoped hybrid retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.deepseek_adapter import llm
from app.domains.knowledge_retrieval.interface import Hit, build_context, cited_sources, retrieve
from app.tools.contracts import OnEvent, Tool, ToolAnswer
from app.tools.turn_context import ChatToolInput, TurnState, last_human_message, to_chat_messages


@dataclass
class RagToolSpec:
    role_prompt: str
    agent_name: str
    filter_topics: set[str] | None = None
    boost_topics: set[str] | None = None


_BASE_SYSTEM_PROMPT = """\
{role_prompt}

## Rule 1 — Answer ONLY from the supplied material
- Base your answer exclusively on the REFERENCE MATERIAL provided below. Do not use \
your own prior knowledge about NUS, this programme, or any other university.
- If the material does not contain the answer, say plainly that the information is not \
in the available sources and advise the user to contact the admissions office at \
msc-dft-admissions@nus.edu.sg. Never guess, never infer, never fill gaps with general \
knowledge.
- Reproduce all numbers, dates, amounts, deadlines and course codes exactly as they \
appear in the material. Do not round, convert, recalculate or paraphrase them.

## Rule 2 — Distinguish official policy from advisory guidance
- Material tagged [official] is official programme information. State it directly.
- Material tagged [advisory] is guidance compiled by this project, not official policy. \
You MUST hedge it with wording such as "we suggest", "as a guide", "you may consider", \
and make clear it is a recommendation rather than an official requirement.
- Never present advisory content as an official rule or requirement.

## Rule 3 — When sources disagree
- ⚠️GOVERNS marks the source to follow on that specific point.
- ⚠️SUPERSEDED marks a source overridden only on that specific point — its other \
content, and its own figures, are still valid and should still be given to the user, \
just reframed as reference points rather than hard requirements.
- Never expose this internal tagging to the user — refer to where information comes \
from in plain language (e.g. "the programme FAQ states ...").

## Rule 4 — Style
- Be accurate, concise, and professional.
- Do not write filler like "according to the reference material".

Reference material:
{context}
"""


def run_rag(spec: RagToolSpec, messages: list, on_event: OnEvent | None = None) -> tuple[str, list[Hit]]:
    """
    Core single-tool RAG step: retrieve (scoped by spec.filter_topics/
    boost_topics), build a tagged context, call the LLM. Returns the plain
    answer text (no Sources footer — callers append that themselves) and
    the Hits used, so a caller merging several tools' answers can also
    merge their sources.

    Shared by each RAG tool's own handler (single-tool path, streamed to
    the user) and the career/comparison tools' legacy-RAG fallback.
    """
    last_user_message = last_human_message(messages)
    if not last_user_message:
        return "I couldn't identify your question. Could you please rephrase it?", []

    hits = retrieve(last_user_message, top_k=5, filter_topics=spec.filter_topics, boost_topics=spec.boost_topics)
    context = build_context(hits) if hits else (
        "No specific programme information is currently available in the "
        "knowledge base. Please contact the admissions office directly."
    )

    system_prompt = _BASE_SYSTEM_PROMPT.format(role_prompt=spec.role_prompt, context=context)
    # max_tokens is generous relative to the expected answer length as a
    # safety margin against truncation.
    chunks: list[str] = []
    for chunk in llm.stream(system_prompt, to_chat_messages(messages), temperature=0.2, max_tokens=2000):
        chunks.append(chunk)
        if on_event is not None:
            on_event({"type": "token", "text": chunk})
    return "".join(chunks), hits


def make_rag_tool(
    name: str,
    role_prompt: str,
    agent_name: str,
    trigger_intents: set[str],
    filter_topics: set[str] | None = None,
    boost_topics: set[str] | None = None,
) -> Tool:
    """Builds a Tool whose handler is a plain-RAG answer scoped to one
    topic."""
    spec = RagToolSpec(role_prompt, agent_name, filter_topics, boost_topics)

    def handler(state: TurnState, on_event: OnEvent | None = None) -> ToolAnswer:
        answer, hits = run_rag(spec, state.messages, on_event=on_event)
        return ToolAnswer(text=answer, sources=cited_sources(hits), agent_used=agent_name)

    return Tool(
        name=name,
        description=role_prompt.strip().splitlines()[0],
        input_model=ChatToolInput,
        handler=handler,
        trigger_intents=frozenset(trigger_intents),
    )


# ── The four plain-RAG specialists ──────────────────────────────────────────

ADMISSIONS_OFFICIAL_SOURCES = """\
- NUS MSc DFinTech Programme Information : https://www.comp.nus.edu.sg/programmes/pg/mdft/
- NUS MSc DFinTech Application Information: https://www.comp.nus.edu.sg/programmes/pg/mdft/application/
- NUS MSc DFinTech Fees and Scholarships  : https://www.comp.nus.edu.sg/programmes/pg/mdft/scholarships/
"""

ADMISSIONS_TOOL = make_rag_tool(
    name="admissions",
    role_prompt=f"""\
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
{ADMISSIONS_OFFICIAL_SOURCES}
""",
    agent_name="admissions_agent",
    trigger_intents={"admissions"},
    boost_topics={"admissions"},
)

ACADEMIC_TOOL = make_rag_tool(
    name="academic",
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
    agent_name="academic_agent",
    trigger_intents={"academic"},
    boost_topics={"academic"},
)

FINANCIAL_TOOL = make_rag_tool(
    name="financial",
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
    agent_name="financial_agent",
    trigger_intents={"financial"},
    boost_topics={"financial"},
)

FAQ_TOOL = make_rag_tool(
    name="faq",
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
    agent_name="faq_agent",
    trigger_intents={"faq"},
    boost_topics={"faq"},
)

# Career/comparison legacy fallback specs — filter_topics (hard-restrict) is
# safe here since these two topics have no overlap elsewhere in the corpus.
CAREER_STYLE_PROMPT = """\
You are the Career Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers career pathways relevant to MSc DFT graduates (e.g. \
Financial Data Science / AI, Compliance / RegTech, and other FinTech-adjacent \
roles), the skills each pathway typically requires, and which programme \
courses build toward a given pathway.

Important: this career-pathway mapping and any course recommendations are \
guidance compiled by this project — NOT an official NUS career placement \
guarantee or official curriculum requirement. Always frame it as suggestion \
("this pathway typically calls for...", "students aiming for this role often \
take..."), never as a rule the student must follow, and never promise \
employment outcomes."""

COMPARISON_STYLE_PROMPT = """\
You are the Programme Comparison Advisor for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your role is to help prospective students compare MSc DFT against other \
universities' FinTech/digital-finance master's programmes, using the \
comparison data and any personal match scores provided.

Hard rules:
- Any personal match score is a transparent, evidence-backed fit signal for \
THIS user (based on their stated skills/profile against each programme's own \
facts) — present it as such, with its reasoning, never as an absolute or \
objective claim that one programme is "better" in general.
- Any information about a competing programme belongs to that university's own \
published sources. Attribute it as such (e.g. "according to [university]'s own \
programme page...") — never present a competitor's information as if it were \
NUS's own, and never present it as independently verified.
- This comparison data (including any match score) is compiled by this project \
for informational purposes, not an official NUS ranking or endorsement. Make \
that clear if the user asks how authoritative the comparison is."""

LEGACY_CAREER_SPEC = RagToolSpec(CAREER_STYLE_PROMPT, "career_agent_fallback", filter_topics={"career"})
LEGACY_COMPARISON_SPEC = RagToolSpec(COMPARISON_STYLE_PROMPT, "comparison_agent_fallback", filter_topics={"comparison"})
