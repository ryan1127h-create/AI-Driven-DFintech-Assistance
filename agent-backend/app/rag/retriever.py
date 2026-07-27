"""
Retriever module — 前端(/api/v1/chat)实际走的检索入口。

【整合】原为本地 ChromaDB + SentenceTransformers;现替换为队友的四层检索
(Supabase pgvector + BM25 + RRF + Cohere rerank)。对外接口完全不变——
`retrieve(query, top_k, domain) -> list[str]`,调用方(admissions_agent /
knowledge_agent)无感知。旧 ChromaDB 实现保留在文件末尾(注释)以便回退。

domain 分类(admissions/academic/financial/general)映射到四层检索的 source_table。
"""

import os
from pathlib import Path

# 四层检索适配器就在同项目的 rag_backend/ 子包里(整合时复制进来的)
from rag_backend.retrieval_api import SupabaseRetriever

# domain -> 四层检索的 source_table 集合。
# 他的 domain(admissions/academic/financial/general)和适配器的 namespace
# (admissions/curriculum/faq)不是一套词,所以这里单独映射到底层 source_table。
_DOMAIN_TO_TABLES: dict[str, set[str]] = {
    "admissions": {"admissions_items", "programme_pages", "application_status_translations"},
    "academic":   {"courses", "course_rules", "career_roles"},
    "financial":  {"programme_pages"},          # 学费/奖学金在网页正文里
    "general":    set(),                         # 空集=不限,全库(见下)
}

# 单例:连接与客户端只建一次,避免每次检索重连
_retriever: SupabaseRetriever | None = None


def _get_retriever() -> SupabaseRetriever:
    global _retriever
    if _retriever is None:
        _retriever = SupabaseRetriever()
    return _retriever


def retrieve(query: str, top_k: int = 3, domain: str = None) -> list[str]:
    """
    Return the top_k most relevant text chunks for the given query.

    Args:
        query:  The user's question.
        top_k:  Number of chunks to return.
        domain: Optional filter ("admissions" | "academic" | "financial" | "general").
                None or "general" searches across all sections.

    返回纯文本列表(与原 ChromaDB 版行为一致),调用方无需改动。
    """
    try:
        r = _get_retriever()
        tables = _DOMAIN_TO_TABLES.get(domain or "", None)
        # 底层适配器按 namespace 过滤;这里改成直接按 source_table 过滤更精确。
        # tables 为空集或 None 都表示不限 domain(全库检索)。
        chunks = r.retrieve_by_tables(query, tables or None, top_k=top_k)
        return [c.text for c in chunks]
    except Exception as exc:
        print(f"[retriever] Warning: 四层检索失败 — {exc}")
        return []


# ============================================================================
# 旧实现(本地 ChromaDB + SentenceTransformers)——保留以便回退。
# 若要切回:恢复下面代码、删除上面的四层检索版即可。
# ============================================================================
# from langchain_community.vectorstores import Chroma
# from langchain_community.embeddings import SentenceTransformerEmbeddings
#
# PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# CHROMA_DIR   = str(PROJECT_ROOT / "chroma_db")
# COLLECTION   = "msc_dft_knowledge"
# EMBED_MODEL  = "all-MiniLM-L6-v2"
# _vectorstore = None
#
# def _get_vectorstore() -> Chroma:
#     global _vectorstore
#     if _vectorstore is None:
#         embeddings = SentenceTransformerEmbeddings(model_name=EMBED_MODEL)
#         _vectorstore = Chroma(persist_directory=CHROMA_DIR,
#                               embedding_function=embeddings, collection_name=COLLECTION)
#     return _vectorstore
#
# def retrieve(query: str, top_k: int = 3, domain: str = None) -> list[str]:
#     try:
#         vs = _get_vectorstore()
#         filter_dict = {"domain": domain} if domain else None
#         docs = vs.similarity_search(query, k=top_k, filter=filter_dict)
#         return [doc.page_content for doc in docs]
#     except Exception as exc:
#         print(f"[retriever] Warning: retrieval failed — {exc}")
#         return []
