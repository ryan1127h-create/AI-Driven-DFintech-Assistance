"""Step 8：把检索结果交给 LLM 生成答案。

检索层（retrieval.py）解决"该看哪几段资料"，这一层解决"怎么把它说成人话"。
四条约束都在 SYSTEM_PROMPT 里，对应需求书 §4：

  8-2 禁止编造   只用给到的资料回答；资料里没有就说没有，不许自己补
  8-3 来源引用   答案末尾给出处（有 url 给链接，没有的给文字出处）
  8-4 冲突呈现   conflict_group 非空时，两种说法都摆出来，标明以哪个为准
  8-5 官方/建议  answer_type=advisory 的必须用"建议/参考"的措辞

用法：
    python answer.py "GMAT 需要多少分?"        # 单个问题
    python answer.py "..." --show-context      # 连检索到的原文一起打印，调 prompt 时用
    python answer.py --limit 10                # 跑 eval_set 前 10 题（调 prompt 用这个，省时间）
    python answer.py --limit 65                # 跑全部（定稿后测）

⚠️ 要在 scripts/ 目录下跑：本脚本 import retrieval。

⚠️ 慢是正常的：Cohere rerank 限流 6.5 秒/次，跑 65 题光等就要 7 分钟。
   NVIDIA 那边是 40 RPM（1.5 秒/次），比 Cohere 宽松得多，所以不用额外限流。
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import retrieval

# NVIDIA 托管的 DeepSeek V4 Pro。OpenAI 兼容接口，复用已装的 openai 包，无新依赖。
# 两个值都可以在 .env 里覆盖：换模型、或改走 DeepSeek 官方 API（同样是 OpenAI 兼容，
# 只需换 base_url + key），代码一行不用动。
LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_LLM_MODEL = "deepseek-ai/deepseek-v4-pro"

# RAG 不需要创造力，需要"照着资料说、每次说的一样"。
# NVIDIA 示例给的是 temperature=1，那是聊天场景的默认值，对我们是有害的：
# 温度越高越发散，越容易把检索到的数字说错。0 同时保证可复现——
# 同一个问题跑两次答案一致，写报告引用时才站得住。
TEMPERATURE = 0
MAX_TOKENS = 1024          # 答案是几句话，给太大只会让它啰嗦
THINKING = False           # 事实型问答用不上思考模式；8-4 冲突题可以试 True 看有无提升

TOP_K = 5                  # 喂给 LLM 的 chunk 数

# 同一个 conflict_group 里有多条被检索到时怎么办：
#   "authoritative_wins" 两条都喂，但告诉 LLM：冲突的那一点以权威方为准，不要复述
#                        被取代的数字；同一条资料里的其他内容照常可用
#   "authoritative_only" 只保留权威那条，另一条连喂都不喂
#   "present_both"       两条并列呈现，说明以哪个为准（需求书 §4 的原始要求）
#
# 当前用 authoritative_wins。为什么不用 authoritative_only：
#   authoritative 是打在**整条 chunk** 上的，但冲突往往只涉及其中**一句话**。
#   实测 page:page_04:2（招生页 Test Scores 节）里只有"GRE 320 / GMAT 650"这一句
#   与 FAQ 冲突，同一条里还有托福 90、雅思 6.0、成绩有效期 5年/2年、印度院校可用
#   GATE 替代——全是别处没有的官方信息。整条丢弃 = 用户问托福时答不上来。
#
# ⚠️ 三种模式都不改数据：原文始终在库里，evaluate.py 的 golden chunk 仍标两条。
#    答辩要讲"如实呈现冲突"就切 present_both，一个常量的事。
CONFLICT_MODE = "authoritative_wins"

# 瞬时失败重试：指数退避 2s → 4s → 8s。见 ask_llm() 的说明。
MAX_RETRIES = 4
RETRY_BASE_WAIT = 2

# 低于这个相关度就判"资料里没有"，直接不调 LLM。
# 暂时关闭（0.0）——阈值要靠 Step 9-3 的 5 道无答案题校准，现在拍脑袋定反而是过早优化。
MIN_RELEVANCE = 0.0

# 低于这个相关度的 chunk 不列进【来源】。
#
# 为什么需要：检索固定返回 TOP_K 条，但真正相关的往往不到 5 条，剩下的位置由
# "最不离谱的"候选填满。实测问 "GMAT 需要多少分"，第 3-5 位是港科大和 NTU 的
# 项目页——主题对（都含 GMAT）、学校错。LLM 正确地忽略了它们，但如果照单全列
# 进来源，用户会以为答案参考了竞品院校资料，比不给来源更误导。
#
# ⚠️ 0.3 是看断层拍的，不是算出来的：那次 rerank 分数是 0.989 / 0.742 / 0.106 /
#    0.056 / 0.054，前二和后三差一个数量级。等 Step 9 有了数据再正经校准。
#    只影响【来源】怎么列，不影响喂给 LLM 的资料。
CITE_MIN_RELEVANCE = 0.3

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --- 8-2/8-4/8-5：约束都写在这里 --------------------------------------------

SYSTEM_PROMPT = """You are the admissions assistant for the NUS Master of Science in \
Digital Financial Technology (MSc DFT). You help prospective students and applicants \
understand the programme, admissions requirements, curriculum, and career pathways.

## Rule 1 — Answer ONLY from the supplied material

- Base your answer exclusively on the REFERENCE MATERIAL provided below. Do not use \
your own prior knowledge about NUS, this programme, or any other university.
- If the material does not contain the answer, say plainly that the information is not \
in the available sources and advise the user to contact the admissions office. \
Never guess, never infer, never fill gaps with general knowledge.
- Reproduce all numbers, dates, amounts, deadlines and course codes exactly as they \
appear in the material. Do not round, convert, recalculate or paraphrase them.

## Rule 2 — Distinguish official policy from advisory guidance

- Material tagged [official] is official programme information. State it directly.
- Material tagged [advisory] is guidance compiled by this project, not official policy. \
You MUST hedge it with wording such as "we suggest", "as a guide", "you may consider", \
and make clear it is a recommendation based on course-to-skill mapping rather than \
an official requirement.
- Never present advisory content as an official rule or requirement.
- For information about competing programmes at other universities, attribute it to \
that university's own published sources — never present it as NUS official information. \
Do not rank programmes or claim one is better than another.

## Rule 3 — When sources disagree

Two official pages sometimes state different things on the same point. Tags tell you \
how to handle it.

- ⚠️SUPERSEDED marks a source overridden **only on whether a requirement is mandatory \
and whether a hard cut-off applies**. On that narrow question, follow the ⚠️GOVERNS \
source: if it says the item is optional and has no minimum threshold, say so plainly \
and do not present the superseded source's figure as a mandatory floor.
- The superseded source's **numbers themselves are still valid official figures** and \
should still be given to the user as guidance — just reframed as reference points \
rather than hard requirements. When both sources give figures, present them together \
as a range or progression (e.g. "X and above, with Y being more competitive") rather \
than as two contradictory rules.
- Everything else in a superseded source is fully valid — a source superseded on \
test-score requirements is still authoritative on English-language requirements, score \
validity periods, and so on.
- ⚠️CONFLICT (if present) means the opposite instruction: show BOTH statements, say \
which to go by, and do not call either one wrong.
- Never expose the internal tagging to the user. Do not write things like "this is \
marked as superseded", "the material is tagged", "source 1 says". Refer to where the \
information actually comes from — e.g. "the programme FAQ states ...", "the admissions \
page states ..." — in plain language.

## Rule 4 — Style

- Reply in the language the question was asked in (Chinese question → Chinese answer, \
English question → English answer).
- Be concise and direct. Lead with the answer, then add necessary detail. Do not restate \
the question.
- Do not write filler like "according to the reference material". Do not invent, guess or \
write out any source links — the system appends sources automatically.
- For questions about admission outcomes or individual eligibility, state that the final \
decision rests with the admissions committee."""


# --- 8-3：出处 -------------------------------------------------------------

# courses 的 source_url 存的是 NUSMods 的 JSON 接口，给用户点开是一堆代码。
# 转成人类可读的课程页面。只在展示时转，不改数据库。
NUSMODS_API = re.compile(r"https?://api\.nusmods\.com/v2/[^/]+/modules/([A-Z0-9]+)\.json")

# 那 50 条没存 source_url 的 chunk（见 check_chunk_fields.py），给文字出处。
# career_roles 没有链接是正确的——它本来就不是官方内容，和 answer_type=advisory 自洽。
FALLBACK_SOURCE = {
    "admissions_items": "NUS MSc DFT 招生要求（官方）",
    "course_rules": "Annex A 培养方案",
    "application_status_translations": "申请状态说明（官方）",
    "career_roles": "职业路径映射 —— 本项目整理，非 NUS 官方内容",
    "knowledge_snippets": "项目 FAQ（官方）",
}


def resolve_conflicts(hits: list[retrieval.Hit]) -> list[retrieval.Hit]:
    """按 CONFLICT_MODE 处理同组冲突。

    只有当同一个 conflict_group 的多条**都被检索到**时才动手：
    只捞到一条时无从比较，原样保留。

    ⚠️ authoritative 单独看没有意义——184 条里 183 条都是 true（那是默认值）。
       只有在 conflict_group 非空、且组内有多条时，这个字段才承载信息。

    authoritative_wins 和 present_both 都不在这里丢数据，交给 prompt 处理。
    """
    if CONFLICT_MODE != "authoritative_only":
        return hits

    groups: dict[str, list[retrieval.Hit]] = {}
    for h in hits:
        if h.conflict_group:
            groups.setdefault(h.conflict_group, []).append(h)

    drop = set()
    for members in groups.values():
        if len(members) > 1 and any(m.authoritative for m in members):
            for m in members:
                if not m.authoritative:
                    drop.add(m.chunk_key)

    return [h for h in hits if h.chunk_key not in drop]


def cited_hits(hits: list[retrieval.Hit], mode: str) -> list[retrieval.Hit]:
    """挑出值得列进【来源】的 chunk。

    ⚠️ 只在 mode=full 时按分数过滤。因为 Hit.score 的含义随模式变：
        full   → Cohere 相关度，0~1，跨问题可比 → 阈值有意义
        vector → 余弦相似度，尺度不同
        hybrid → RRF 融合分，只反映排名不反映相关度
    拿同一个阈值卡三种分数，等于拿摄氏度当公斤用（retrieval.py 里 fuse_rrf
    的注释解释过同样的道理）。所以其他模式一律全列，不做过滤。

    另外保底至少留 1 条：宁可列一条弱的，也不要出现"有答案却没有出处"。
    """
    if mode != "full":
        return hits
    kept = [h for h in hits if h.score >= CITE_MIN_RELEVANCE]
    return kept or hits[:1]


def source_of(hit: retrieval.Hit) -> str:
    """一条 chunk 的出处：优先给链接，没有就给文字说明。

    8-3 不依赖 source_url 补全——现在 134/184 有链接，剩下的给文字出处照样能交代来源。
    等"补 source_url"那条任务做完，链接会自动出现，这里一行都不用改。
    """
    md = hit.metadata if isinstance(hit.metadata, dict) else {}
    url = md.get("source_url")
    if url:
        m = NUSMODS_API.match(url)
        return f"https://nusmods.com/courses/{m.group(1)}" if m else url

    label = FALLBACK_SOURCE.get(hit.source_table, hit.source_table)
    # 培养方案分届别，不标清楚会误导（2026 届和 2025 届规则不同）
    if hit.source_table == "course_rules" and md.get("intake"):
        label += f"（{md['intake']} 届）"
    return label


# --- 组装喂给 LLM 的资料 -----------------------------------------------------

def build_context(hits: list[retrieval.Hit]) -> str:
    """把 chunk 拼成【参考资料】。

    每条都带上 [official]/[advisory] 标记，让 LLM 知道该用什么口气——
    这是 8-5 的落地方式：类型在切片时就按数据来源写死在库里了，不靠 LLM 判断。
    """
    # 8-4：先找出哪些 chunk 属于冲突组，且组内谁是权威。
    # ⚠️ authoritative 单独看没有意义——184 条里 183 条都是 true（默认值）。
    #    只有在 conflict_group 非空时，这个字段才承载信息。
    conflict_members: dict[str, list[retrieval.Hit]] = {}
    for h in hits:
        if h.conflict_group:
            conflict_members.setdefault(h.conflict_group, []).append(h)

    blocks = []
    for i, h in enumerate(hits, 1):
        tags = [f"[{h.answer_type}]"]
        # 同一冲突组的多条都被检索到了，才需要提示。只捞到一条时不提示——
        # 否则等于请 LLM 去编另一种说法。
        if h.conflict_group and len(conflict_members[h.conflict_group]) > 1:
            if CONFLICT_MODE == "authoritative_wins":
                tags.append("⚠️GOVERNS this topic" if h.authoritative else
                            "⚠️SUPERSEDED on whether the requirement is mandatory "
                            "and whether a hard cut-off applies — but its factual "
                            "figures and all its other content remain valid")
            else:
                tags.append("⚠️CONFLICT: official pages disagree on this point; "
                            "present both statements to the user.")
                tags.append("(THIS ONE TAKES PRECEDENCE)" if h.authoritative
                            else "(does not take precedence, but is also a "
                                 "current official page)")

        head = f"[SOURCE {i}] {' '.join(tags)}"
        body = f"{h.context}\n{h.content}" if h.context else h.content
        blocks.append(f"{head}\n{body}")

    return "\n\n".join(blocks)


def ask_llm(client, question: str, context: str, model: str) -> str:
    """调 LLM 生成答案，失败自动重试。

    为什么需要重试：实测 NVIDIA 端点对某个模型的**第一次**调用会返回 404
    （后端冷启动，模型名本身是对的——它在 /v1/models 列表里），几秒后即恢复。
    单次手动跑无所谓，重跑一次就是；但 Step 9 要连跑 65 题，中间任何一次瞬时
    失败都会让整轮评估崩在半路，前面二十分钟白跑。
    见 diagnose_llm.py 的排查记录。
    """
    import time

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",
                     "content": f"REFERENCE MATERIAL\n{context}\n\nQUESTION\n{question}"},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                extra_body={"chat_template_kwargs": {"thinking": THINKING}},
                stream=False,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_WAIT * (2 ** attempt)   # 2s, 4s, 8s
                print(f"    ⚠️ 第 {attempt + 1} 次调用失败（{type(e).__name__}），{wait}s 后重试")
                time.sleep(wait)

    raise RuntimeError(f"调用 LLM 连续失败 {MAX_RETRIES} 次：{last_err}") from last_err


# --- 主流程 -----------------------------------------------------------------

def answer(conn, oa_client, llm_client, question: str, model: str = DEFAULT_LLM_MODEL,
           k: int = TOP_K, mode: str = "full", show_context: bool = False) -> dict:
    """一问一答。返回 dict 便于 Step 9 直接拿去评估。"""
    hits = retrieval.retrieve(conn, oa_client, question, k=k, mode=mode)
    hits = resolve_conflicts(hits)   # 冲突组按 CONFLICT_MODE 取舍，在喂给 LLM 之前

    if not hits or (MIN_RELEVANCE and hits[0].score < MIN_RELEVANCE):
        # 检索不到就别调 LLM——没有资料还让它答，就是在请它编
        return {"question": question, "answer": "提供的资料中没有这项信息，建议直接联系招生办确认。",
                "hits": hits, "sources": [], "llm_called": False}

    context = build_context(hits)
    if show_context:
        print(f"\n--- 喂给 LLM 的资料 ---\n{context}\n--- 资料结束 ---\n")

    text = ask_llm(llm_client, question, context, model)

    # 出处按 chunk 顺序去重（同一个 FAQ 页面可能命中多条，只列一次），
    # 并滤掉明显不相关的——见 CITE_MIN_RELEVANCE 的说明。
    sources, seen = [], set()
    for h in cited_hits(hits, mode):
        s = source_of(h)
        if s not in seen:
            seen.add(s)
            sources.append((s, h.answer_type))

    return {"question": question, "answer": text, "hits": hits,
            "sources": sources, "llm_called": True}


def show(result: dict) -> None:
    print(f"\n{'=' * 78}\n问题：{result['question']}\n{'=' * 78}")
    print(f"\n【答案】\n{result['answer']}")

    if result["sources"]:
        print("\n【来源】")
        for i, (src, at) in enumerate(result["sources"], 1):
            tag = "官方" if at == "official" else "建议/参考"
            print(f"  {i}. {src}  （{tag}）")

    # 检索命中一起打出来，方便判断"答得不好"是检索的锅还是 prompt 的锅
    hits = result["hits"]
    if hits:
        keys = ", ".join(f"{h.chunk_key}({h.score:.3f})" for h in hits)
        print(f"\n  检索命中：{keys}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?", help="要问的问题")
    p.add_argument("-k", type=int, default=TOP_K, help=f"喂给 LLM 几条 chunk（默认{TOP_K}）")
    p.add_argument("--mode", choices=["vector", "hybrid", "full"], default="full")
    p.add_argument("--limit", type=int, metavar="N",
                   help="改跑 eval_set.jsonl 的前 N 题（调 prompt 时用小的，省时间）")
    p.add_argument("--show-context", action="store_true", help="打印喂给 LLM 的资料原文")
    args = p.parse_args()

    if not args.query and not args.limit:
        p.error("给一个问题，或者用 --limit N 跑评估集")

    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    oa_key = os.getenv("OPENAI_API_KEY", "").strip()
    llm_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not db or not oa_key:
        raise SystemExit("需要 .env 里的 DATABASE_URL 和 OPENAI_API_KEY")
    if not llm_key:
        raise SystemExit("需要 .env 里的 NVIDIA_API_KEY（build.nvidia.com 上申请，nvapi- 开头）")

    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL
    base_url = os.getenv("LLM_BASE_URL", "").strip() or LLM_BASE_URL

    from openai import OpenAI
    oa_client = OpenAI(api_key=oa_key)                                  # embedding 用
    llm_client = OpenAI(base_url=base_url, api_key=llm_key)             # 生成答案用
    print(f"模型：{model}  @  {base_url}")

    questions = [args.query]
    if args.limit:
        path = DATA_DIR / "eval_set.jsonl"
        with path.open(encoding="utf-8") as f:
            questions = [json.loads(line)["question"] for line in f if line.strip()][:args.limit]
        print(f"跑 {path.name} 前 {len(questions)} 题"
              f"（Cohere 限流 6.5 秒/次，预计 {len(questions) * 7 // 60} 分 {len(questions) * 7 % 60} 秒）")

    with psycopg.connect(db) as conn:
        for q in questions:
            show(answer(conn, oa_client, llm_client, q, model=model,
                        k=args.k, mode=args.mode, show_context=args.show_context))
    print()


if __name__ == "__main__":
    main()
