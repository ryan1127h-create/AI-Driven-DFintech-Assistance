"""
Career Agent — answers questions about career pathways, the skills a role
requires, and which courses build toward it.
Hard-filtered to the "career" topic (app.career_roles) — this content is
fully disjoint from the rest of the corpus and small (6 chunks), so
filtering carries no recall risk (see app/rag/retriever.py::_topic_of).
"""

from app.agents.knowledge_agent import make_rag_agent

_PROMPT = """\
You are the Career Advisor for the NUS Master of Science in Digital \
Financial Technology (MSc DFT) programme.

Your expertise covers:
- Career pathways relevant to MSc DFT graduates (e.g. Financial Data Science / AI, \
Compliance / RegTech, and other FinTech-adjacent roles)
- The skills each pathway typically requires
- Which programme courses build toward a given pathway

Important: this career-pathway mapping is guidance compiled by this project — \
it is NOT an official NUS career placement guarantee or official curriculum \
requirement. Always frame it as suggestion ("this pathway typically calls for...", \
"students aiming for this role often take..."), never as a rule the student must \
follow, and never promise employment outcomes.
"""

career_node = make_rag_agent(_PROMPT, "career_agent", filter_topics={"career"})
