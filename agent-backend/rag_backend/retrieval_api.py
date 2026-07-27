"""检索适配器：把四层检索(retrieval.py)包成 xzy 后端能调用的形状。

xzy 的 agent 通过一个可插拔的 Retriever Protocol 调检索(见
backend-xzy/common/retriever.py 的 `class Retriever(Protocol)`)：

    retrieve(query, namespace=None, top_k=3) -> list[RetrievalChunk]

其中 RetrievalChunk 只有三个字段 (text, source_id, score)。本文件提供
`SupabaseRetriever`：外壳符合他的 Protocol，内核完全是我们的四层检索——
检索逻辑一行没改，只做「参数翻译 + 结果翻译 + namespace 过滤」。

对接方式：xzy 侧把 `common.retriever` 的实例换成本类即可，他的 confidence
门控 / agent / 测试都不用动(那正是他 Protocol 设计的意义)。

⚠️ score 语义提醒：本类返回的 score 是 Cohere rerank 相关度，和 xzy 原来
BM25 的「IDF 覆盖率绝对分」不是一个尺度。他 §0.2 的门控阈值
(0.60/0.72/0.80) 是按旧检索校准的，换本检索后必须重新校准(见校准任务)。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from dotenv import load_dotenv

# 兼容两种运行方式：单独跑本文件(import retrieval)/ 作为包被 xzy 导入(from . import)
try:
    from . import retrieval
except ImportError:
    import retrieval


# --- 与 xzy 的 RetrievalChunk 对齐 ---------------------------------------------
# 复制一份同形状的 dataclass，避免硬依赖 backend-xzy 的包路径(两个仓库独立)。
# 字段与 backend-xzy/common/confidence.py 的 RetrievalChunk 完全一致；
# 对接时若直接跑在他仓库内，可改为 `from common.confidence import RetrievalChunk`。
@dataclass(frozen=True)
class RetrievalChunk:
    text: str
    source_id: str | None = None
    score: float | None = None


# --- namespace 映射 -----------------------------------------------------------
# xzy 的知识库分三类(admissions/curriculum/faq)。我们的库按 source_table 分 8 类，
# 归并到他的 namespace 上。competitor_programs 不并入任何 namespace——竞品对比走
# 他自己的 #6 Comparator + programs_dataset.json，不该混进 RAG 检索。
NAMESPACE_TO_TABLES: dict[str, set[str]] = {
    "admissions": {"admissions_items", "programme_pages", "application_status_translations"},
    "curriculum": {"courses", "course_rules"},
    "faq": {"knowledge_snippets"},
    # career_roles 是 advisory 的职业映射，问职业/选课时也有用；归到 curriculum
    # 让 #7 选课/职业 agent 能检索到。
}
NAMESPACE_TO_TABLES["curriculum"].add("career_roles")

# 检索时永远排除的表(即便 namespace=None 全库检索也不返回)——竞品数据归 #6。
_EXCLUDE_TABLES = {"competitor_programs"}


def _tables_for(namespace: str | None) -> set[str] | None:
    """namespace -> 允许的 source_table 集合。None 表示不限(全库，但仍排除竞品)。"""
    if namespace is None:
        return None
    return NAMESPACE_TO_TABLES.get(namespace, set())


class SupabaseRetriever:
    """实现 xzy 的 Retriever Protocol，内核是我们的四层检索。

    用法(在 xzy 后端里)：
        retriever = SupabaseRetriever()
        chunks = retriever.retrieve("推荐信要求", namespace="admissions", top_k=3)

    连接与客户端在实例内长驻，避免每次检索重连(psycopg 连接 + OpenAI embedding
    客户端复用)。mode 固定 "full" 走完整四层；调低成本可传 "hybrid"。
    """

    def __init__(self, mode: str = "full") -> None:
        # 明确加载本文件同目录的 .env——被 xzy 从别的工作目录导入时，
        # 默认的 load_dotenv() 会在错误的目录找不到 .env。
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        load_dotenv()  # 再兜底找一次当前目录（单独跑本文件时）
        db = os.getenv("DATABASE_URL", "").strip()
        oa_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not db or not oa_key:
            raise SystemExit("需要 .env 里的 DATABASE_URL 和 OPENAI_API_KEY")
        from openai import OpenAI
        self._conn = psycopg.connect(db)
        self._oa = OpenAI(api_key=oa_key)
        self._mode = mode

    def retrieve(self, query: str, namespace: str | None = None,
                 top_k: int = 3) -> list[RetrievalChunk]:
        allowed = _tables_for(namespace)
        # namespace 给了但不认识 -> 没有对应内容，返回空(而不是全库)
        if namespace is not None and not allowed:
            return []

        # 多捞一些候选，过滤 namespace/竞品后再截 top_k——避免过滤后不足数。
        raw = retrieval.retrieve(self._conn, self._oa, query,
                                 k=max(top_k * 4, 20), mode=self._mode)

        out: list[RetrievalChunk] = []
        for h in raw:
            if h.source_table in _EXCLUDE_TABLES:
                continue
            if allowed is not None and h.source_table not in allowed:
                continue
            out.append(RetrievalChunk(text=h.content,
                                      source_id=h.chunk_key,
                                      score=round(float(h.score), 4)))
            if len(out) >= top_k:
                break
        return out

    def close(self) -> None:
        self._conn.close()


# --- 自测 CLI -----------------------------------------------------------------
# 直接跑本文件可验证适配器输出格式对不对，不依赖 xzy 的代码。
#     python retrieval_api.py "推荐信要求" --namespace admissions
def _main() -> None:
    import argparse
    import json

    p = argparse.ArgumentParser(description="检索适配器自测")
    p.add_argument("query")
    p.add_argument("--namespace", choices=["admissions", "curriculum", "faq"], default=None)
    p.add_argument("--top-k", type=int, default=3)
    args = p.parse_args()

    r = SupabaseRetriever()
    try:
        chunks = r.retrieve(args.query, namespace=args.namespace, top_k=args.top_k)
    finally:
        r.close()

    print(f"\nquery={args.query!r}  namespace={args.namespace}  →  {len(chunks)} 条\n")
    for i, c in enumerate(chunks, 1):
        print(f"{i}. [{c.score}] {c.source_id}")
        print(f"   {c.text[:110].replace(chr(10), ' ')}...")
    # 也打印一份 JSON，就是 xzy 会收到的形状
    print("\n--- 他会收到的 JSON ---")
    print(json.dumps({"chunks": [c.__dict__ for c in chunks]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
