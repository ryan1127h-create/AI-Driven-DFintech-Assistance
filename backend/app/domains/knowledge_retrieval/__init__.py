"""
Knowledge retrieval — hybrid search (vector + BM25 + reciprocal rank
fusion) over the shared knowledge base, plus the prompt-context and
citation formatting every retrieval-grounded answer needs. A generic
supporting domain, not a user-facing bounded context: it owns no data of
its own (reads through the knowledge base adapter) and exposes no HTTP
routes — other domains and the orchestrator call it directly for
"find the relevant chunks for this query" and "format them for a prompt".
"""
