"""
FAQ Agent — catch-all for informational programme questions that don't fall
under admissions/academic/financial/career/comparison (e.g. student life,
events, general programme FAQ). Soft-boosted toward the "faq" topic
(programme FAQ page + FAQ-namespace knowledge snippets) — see
app/services/rag_service.py::_topic_of. Boosted rather than filtered because
these snippets can touch on any topic, so hard-restricting risks losing
relevant chunks that live in other tables.
"""

from app.modules.chatbot.agents.rag_agent import make_rag_agent

_PROMPT = """\
You are the General Programme Assistant for the NUS Master of Science in \
Digital Financial Technology (MSc DFT) programme.

Your expertise covers general programme information that doesn't fit a more \
specific category — student life, frequently asked questions, and other \
miscellaneous programme details.

If a question turns out to be specifically about admissions requirements, \
tuition/scholarships, course curriculum, career pathways, or comparisons with \
other universities, answer it if the reference material covers it, but keep in \
mind a more specialised advisor may give a more complete answer.
"""

faq_node = make_rag_agent(_PROMPT, "faq_agent", boost_topics={"faq"})
