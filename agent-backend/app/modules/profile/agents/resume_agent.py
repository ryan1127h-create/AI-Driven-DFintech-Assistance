"""
Resume profile agent — a single-purpose extraction agent, deliberately NOT
wired into the chatbot's intent-classifying supervisor graph (see
app/modules/chatbot/agents/supervisor.py). Invoked directly and only by
app/modules/profile/service.py, itself called from one dedicated endpoint
(POST /api/v1/profile/resume). One LLM call, no routing.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.deepseek_client import build_chat_llm
from app.modules.profile.constants import ACADEMIC_BACKGROUND_VALUES, TARGET_ROLE_VALUES, TECH_LEVEL_VALUES

_EXTRACTION_PROMPT = f"""\
You extract structured applicant facts from a resume/CV, for an NUS MSc \
DFinTech admissions assistant. Read the resume text provided and return \
ONLY a JSON object with the fields below — omit any field the resume does \
not clearly support. Do not guess or invent values.

Fields (all optional, omit what the resume doesn't support):
- academic_background_raw: the applicant's degree title/major, close to their own wording
- academic_background_std: one of {ACADEMIC_BACKGROUND_VALUES} — best-fit category for academic_background_raw
- school_tier: free text describing the school's tier if inferrable (e.g. "985", "QS100"), else omit
- tech_level_raw: a short description of the applicant's technical/programming skill level, in your own summary of the evidence
- tech_level_std: one of {TECH_LEVEL_VALUES} — only if clearly supported by the resume, else omit
- work_years: integer, total years of relevant work experience
- gmat: integer test score if mentioned, else omit
- gre: integer test score if mentioned, else omit
- toefl: integer test score if mentioned, else omit
- ielts: number test score if mentioned, else omit
- target_role_raw: the applicant's stated or clearly implied target career/role, in your own words
- target_role_std: one of {TARGET_ROLE_VALUES} — only if it clearly matches one of these, else omit
- target_industry_raw: the applicant's stated or clearly implied target industry, in your own words
- target_industry_std: a short lowercase category for target_industry_raw, else omit
- application_term: free text if the resume mentions an intended application term (e.g. "2026 Fall"), else omit
- intake_year: integer, only if the resume explicitly states an intended NUS intake year, else omit
- completed_courses: array of relevant prior course codes or course titles explicitly mentioned in the resume, especially computing, finance, math, statistics, data, AI, fintech, or programming courses; omit if none are clearly listed

Respond with ONLY the JSON object, no markdown, no explanation. If a field \
is not supported by the resume text, omit it entirely rather than guessing."""


def extract_profile_from_resume(resume_text: str) -> dict:
    """One LLM call. Raises on failure (unlike the old per-turn extraction
    this replaces, this runs synchronously as the primary action of its own
    endpoint, so a failure should surface as an HTTP error, not be swallowed)."""
    # max_tokens is generous relative to the expected JSON output as a
    # safety margin against truncation.
    llm = build_chat_llm(temperature=0, max_tokens=1500)
    response = llm.invoke([
        SystemMessage(content=_EXTRACTION_PROMPT),
        HumanMessage(content=resume_text),
    ])
    result = json.loads(response.content.strip())
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object from the extraction model, got: {result!r}")
    return result
