"""
Retriever module — singleton ChromaDB wrapper with optional domain filtering.

Domain values match the 'domain' metadata written by ingest.py:
  "admissions" | "academic" | "financial" | "general"

Pass domain=None to search across all sections (used by assessment_node).
"""

from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR   = str(PROJECT_ROOT / "chroma_db")
COLLECTION   = "msc_dft_knowledge"
EMBED_MODEL  = "all-MiniLM-L6-v2"

_vectorstore = None


def _get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        embeddings = SentenceTransformerEmbeddings(model_name=EMBED_MODEL)
        _vectorstore = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings,
            collection_name=COLLECTION,
        )
    return _vectorstore


def retrieve(query: str, top_k: int = 3, domain: str = None) -> list[str]:
    """
    Return the top_k most relevant text chunks for the given query.

    Args:
        query:  The user's question.
        top_k:  Number of chunks to return.
        domain: Optional metadata filter ("admissions", "academic", "financial").
                When None, searches across all sections.
    """
    try:
        vs = _get_vectorstore()
        filter_dict = {"domain": domain} if domain else None
        docs = vs.similarity_search(query, k=top_k, filter=filter_dict)
        return [doc.page_content for doc in docs]
    except Exception as exc:
        print(f"[retriever] Warning: retrieval failed — {exc}")
        return []
