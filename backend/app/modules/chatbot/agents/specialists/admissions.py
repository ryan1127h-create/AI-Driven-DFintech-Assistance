"""
Admissions Agent — answers factual questions about admission requirements,
application process, eligibility, and deadlines. Uses domain-filtered RAG
(domain="admissions"). See app/modules/chatbot/agents/specialists/assessment.py
for the personalised Application Readiness Assessment node, which shares
OFFICIAL_SOURCES with this module.
"""

from app.modules.chatbot.agents.rag_agent import make_rag_agent

OFFICIAL_SOURCES = """\
- NUS MSc DFinTech Programme Information : https://www.comp.nus.edu.sg/programmes/pg/mdft/
- NUS MSc DFinTech Application Information: https://www.comp.nus.edu.sg/programmes/pg/mdft/application/
- NUS MSc DFinTech Fees and Scholarships  : https://www.comp.nus.edu.sg/programmes/pg/mdft/scholarships/
"""

_ADMISSIONS_PROMPT = f"""\
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
{OFFICIAL_SOURCES}
"""

admissions_node = make_rag_agent(_ADMISSIONS_PROMPT, "admissions_agent", boost_topics={"admissions"})
