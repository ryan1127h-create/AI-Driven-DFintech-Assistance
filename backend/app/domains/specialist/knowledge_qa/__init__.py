"""
Knowledge QA — answers a programme-facts question strictly from the shared
knowledge base, for one of four fixed topics (admissions, academic,
financial, faq) plus a generic role-prompt escape hatch other specialists
can reuse (see program_comparison's legacy-RAG fallback). Built on top of
app.domains.knowledge_retrieval, which owns retrieval itself (hybrid
search, caching, context/citation formatting) and has no opinion on how a
retrieved context gets turned into an answer — that generation step is
this domain's only job.
"""
