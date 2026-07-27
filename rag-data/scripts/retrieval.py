"""四层检索：向量 + BM25 + RRF 融合 + Cohere Rerank。

见 docs/检索层具体说明.md。四层各自解决一个问题：

  ① 向量 (search_vector)  按"意思"找。短板：FT5005/FT5009 这类代号易混、跨语言有损耗。
  ② BM25  (search_bm25)   按"词"找。精确命中代号/数字，补①的短板。不懂意思。
  ③ RRF   (fuse_rrf)      两路排名融合。两路都命中的自动浮上来。
  ④ Rerank(rerank)        把问题和 chunk 原文一起给模型精读，压掉"看着像但答不对题"的。

用法：
    python scripts/retrieval.py "学费多少钱?"                  # 走完四层
    python scripts/retrieval.py "学费多少钱?" --mode vector    # 只用①，看基线
    python scripts/retrieval.py "学费多少钱?" --mode hybrid    # ①②③，不 rerank
    python scripts/retrieval.py "学费多少钱?" --compare        # 三种模式并排对比

--mode 用于 Step 7 的消融对比：测出每加一层，Pass@k 涨多少。
"""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

APP_SCHEMA = "app"
EMBED_MODEL = "text-embedding-3-small"
RERANK_MODEL = "rerank-multilingual-v3.0"  # 多语言版：用户会用中文提问

# ③ RRF 权重：语义为主、关键词补充（跟随 Anthropic cookbook 默认值）。
# 可用评估集测出最优比例。
W_SEMANTIC = 0.8
W_BM25 = 0.2

# ①② 各自先捞这么多候选交给 ③ 融合（宁滥勿缺，靠 ④ 精挑）。
# 语料只有 184 条，所以取 50 已经够宽。
RECALL_K = 50


@dataclass
class Hit:
    """一条检索结果。score 的含义随层不同：向量=余弦相似度，BM25=词频分，
    RRF=融合分，Rerank=相关度。跨层不可比，所以只看排名。"""
    chunk_key: str
    source_table: str
    content: str
    context: str
    answer_type: str
    conflict_group: str | None
    authoritative: bool
    score: float
    metadata: dict | None = None   # source_url 在这里，Step 8 生成答案时要给出处
    from_vector: bool = False
    from_bm25: bool = False


# --- 数据加载 ---------------------------------------------------------------

_CHUNKS: list[dict] | None = None
_BM25 = None


def load_chunks(conn: psycopg.Connection) -> list[dict]:
    """把全部 chunk 读进内存。184 条，BM25 直接在内存算，不需要 Elasticsearch。"""
    global _CHUNKS
    if _CHUNKS is None:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
                select chunk_key, source_table, source_id, content, context,
                       answer_type, conflict_group, authoritative, metadata
                from {APP_SCHEMA}.document_chunks
                order by id
            """)
            _CHUNKS = cur.fetchall()
    return _CHUNKS


def tokenize(text: str) -> list[str]:
    """BM25 的分词。英文按词，中文按字。

    中文没有空格，所以每个汉字单独成 token —— 这样"学费"能匹配到含"学费"的文本
    （拆成 学+费 两个 token 分别匹配）。对我们这种中英混排的语料够用了。
    """
    text = text.lower()
    # 英文/数字词（保留 ft5005、s$74,120 这类）
    latin = re.findall(r"[a-z0-9][a-z0-9$,.\-]*", text)
    # 中文字符逐字
    han = re.findall(r"[一-鿿]", text)
    return latin + han


# --- ① 向量检索 -------------------------------------------------------------

def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def search_vector(conn, client, query: str, k: int = RECALL_K) -> list[Hit]:
    """① 向量检索：问题转向量，在 pgvector 里找坐标最近的 chunk（余弦相似度）。

    按"意思"检索——用户问"要花多少钱"能命中写着 tuition fee 的 chunk，一个字不重合。
    chunk 的向量是切片时就算好的（那时还不知道会被问什么），所以对 FT5005/FT5009
    这类高度相似的代号区分度低 —— 这正是 ② BM25 要补的。
    """
    qvec = to_pgvector(client.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select chunk_key, source_table, content, context, answer_type,
                   conflict_group, authoritative, metadata,
                   1 - (embedding <=> %s::vector) as sim
            from {APP_SCHEMA}.document_chunks
            order by embedding <=> %s::vector
            limit %s
        """, (qvec, qvec, k))
        return [
            Hit(chunk_key=r["chunk_key"], source_table=r["source_table"],
                content=r["content"], context=r["context"],
                answer_type=r["answer_type"], conflict_group=r["conflict_group"],
                authoritative=r["authoritative"], score=r["sim"],
                metadata=r["metadata"], from_vector=True)
            for r in cur.fetchall()
        ]


# --- ② BM25 关键词检索 ------------------------------------------------------

def search_bm25(conn, query: str, k: int = RECALL_K) -> list[Hit]:
    """② BM25：不看意思，只数词——哪个 chunk 里出现了问题里的词、出现几次。

    正因为"死板"，它在我们的语料上很关键：FT5005 / IT5001X / GMAT 650 / S$74,120
    这些精确代号和数字，向量容易混淆（FT5005 和 FT5009 的向量极其接近），
    BM25 一眼认出。而且数字/代号中英文一样，天然跨语言。

    索引建在 (context + content) 上，和 embedding 用同一份文本 —— 这样我们加的
    context 前缀（项目名、技能中文别名）同时惠及向量和 BM25。
    即 cookbook 里的 "Contextual BM25"。
    """
    global _BM25
    from rank_bm25 import BM25Okapi

    chunks = load_chunks(conn)
    if _BM25 is None:
        corpus = [tokenize(f"{c['context'] or ''}\n{c['content']}") for c in chunks]
        _BM25 = BM25Okapi(corpus)

    scores = _BM25.get_scores(tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    hits = []
    for i in ranked:
        if scores[i] <= 0:      # 一个词都没匹配上，别塞进候选
            continue
        c = chunks[i]
        hits.append(Hit(
            chunk_key=c["chunk_key"], source_table=c["source_table"],
            content=c["content"], context=c["context"],
            answer_type=c["answer_type"], conflict_group=c["conflict_group"],
            authoritative=c["authoritative"], score=float(scores[i]),
            metadata=c["metadata"], from_bm25=True))
    return hits


# --- ③ RRF 融合 -------------------------------------------------------------

def fuse_rrf(vector_hits: list[Hit], bm25_hits: list[Hit], k: int) -> list[Hit]:
    """③ RRF：把①②两份排名合并成一份。

    为什么不能直接把分数相加：向量相似度是 0~1 的余弦值，BM25 分数是没有上界的
    词频统计值 —— 量纲不同，相加没有意义（等于拿摄氏度加公斤）。

    RRF 的解法：只看排第几，不看分数。
        score = W_SEMANTIC × 1/(向量排名) + W_BM25 × 1/(BM25排名)
    排第1贡献 1/1，排第10贡献 1/10。两路都命中的 chunk 拿到双份加成 → 自动浮上来。
    "两路都认可的，八成是对的。"
    """
    v_rank = {h.chunk_key: i for i, h in enumerate(vector_hits)}
    b_rank = {h.chunk_key: i for i, h in enumerate(bm25_hits)}
    by_key = {h.chunk_key: h for h in vector_hits}
    for h in bm25_hits:
        by_key.setdefault(h.chunk_key, h)

    fused = []
    for key, hit in by_key.items():
        score = 0.0
        if key in v_rank:
            score += W_SEMANTIC * (1 / (v_rank[key] + 1))
        if key in b_rank:
            score += W_BM25 * (1 / (b_rank[key] + 1))
        hit.score = score
        hit.from_vector = key in v_rank
        hit.from_bm25 = key in b_rank
        fused.append(hit)

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:k]


# --- ④ Cohere Rerank --------------------------------------------------------

# Cohere Trial key 限速：每分钟 10 次。批量评估时保证两次调用间隔 ≥ 这个秒数。
COHERE_MIN_INTERVAL = 6.5
_co_client = None
_last_rerank_at = 0.0


def _cohere():
    global _co_client
    if _co_client is None:
        import cohere
        key = os.getenv("COHERE_API_KEY", "").strip()
        if not key:
            raise SystemExit("COHERE_API_KEY 缺失，请加进 .env")
        _co_client = cohere.ClientV2(api_key=key)
    return _co_client


def rerank(query: str, candidates: list[Hit], k: int) -> list[Hit]:
    """④ Rerank：把问题和 chunk 原文一起交给 cross-encoder 模型精读打分。

    ①②③ 都是"隔空比对"——chunk 的向量在切片时就冻结了，那时还不知道用户会问什么。
    所以"NUS和NTU比怎么样"会把只讲 NUS 考试要求的 Test Scores 节排到第2位
    （因为都含 GMAT 等词，数字上看着像）。

    Rerank 不一样：它同时看到问题和 chunk 原文，能推理"这段没提 NTU，答不了对比"
    → 打低分压下去。代价是慢（每个候选跑一次模型），所以只对①②③海选出的候选做。

    Trial key 限每分钟 10 次，所以两次调用间隔至少 COHERE_MIN_INTERVAL 秒。
    真实场景一次只 rerank 一个问题，碰不到这个限制；只有批量评估才会。
    """
    import time

    global _last_rerank_at
    wait = COHERE_MIN_INTERVAL - (time.time() - _last_rerank_at)
    if wait > 0:
        time.sleep(wait)

    co = _cohere()
    # 和 embedding 一样喂 context + content，让模型看到完整信息
    docs = [f"{h.context or ''}\n{h.content}" for h in candidates]
    resp = co.rerank(model=RERANK_MODEL, query=query, documents=docs, top_n=min(k, len(docs)))
    _last_rerank_at = time.time()

    out = []
    for r in resp.results:
        hit = candidates[r.index]
        hit.score = r.relevance_score
        out.append(hit)
    return out


# --- 统一入口 ---------------------------------------------------------------

def retrieve(conn, client, query: str, k: int = 5, mode: str = "full") -> list[Hit]:
    """统一检索入口。mode 控制走几层，供 Step 7 消融对比：

        vector : 只用 ①            （基线）
        hybrid : ① + ② + ③        （混合检索，不 rerank）
        full   : ① + ② + ③ + ④    （完整四层）
    """
    if mode == "vector":
        return search_vector(conn, client, query, k)

    v = search_vector(conn, client, query, RECALL_K)
    b = search_bm25(conn, query, RECALL_K)
    fused = fuse_rrf(v, b, RECALL_K)

    if mode == "hybrid":
        return fused[:k]
    return rerank(query, fused, k)


# --- CLI --------------------------------------------------------------------

def show(hits: list[Hit], title: str) -> None:
    print(f"\n{title}")
    print("-" * 78)
    for i, h in enumerate(hits, 1):
        src = []
        if h.from_vector:
            src.append("向量")
        if h.from_bm25:
            src.append("BM25")
        tag = f"[{'+'.join(src)}]" if src else ""
        conflict = f"  ⚠️{h.conflict_group}" if h.conflict_group else ""
        print(f"{i}. [{h.score:.3f}] {h.chunk_key}  ({h.source_table}) {tag}{conflict}")
        print(f"     {h.content[:88].replace(chr(10), ' ')}...")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", help="要检索的问题")
    p.add_argument("-k", type=int, default=5, help="返回几条（默认5）")
    p.add_argument("--mode", choices=["vector", "hybrid", "full"], default="full")
    p.add_argument("--compare", action="store_true", help="三种模式并排对比")
    args = p.parse_args()

    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not db or not key:
        raise SystemExit("需要 .env 里的 DATABASE_URL 和 OPENAI_API_KEY")

    from openai import OpenAI
    client = OpenAI(api_key=key)

    with psycopg.connect(db) as conn:
        print(f"\n问题: {args.query}")
        if args.compare:
            show(retrieve(conn, client, args.query, args.k, "vector"), "① 只用向量（基线）")
            show(retrieve(conn, client, args.query, args.k, "hybrid"), "①②③ 向量+BM25+RRF")
            show(retrieve(conn, client, args.query, args.k, "full"), "①②③④ 加 Rerank")
        else:
            show(retrieve(conn, client, args.query, args.k, args.mode), f"mode={args.mode}")


if __name__ == "__main__":
    main()
