"""Step 7: Pass@k 评估 + 消融对比。

拿 data/eval_set.jsonl 的标注题，对每种检索模式跑一遍，算 Pass@k：
一道题检索出的 top-k 里，只要含任一 golden chunk 就算命中（golden 可能多条，
互为同义 chunk）。命中率 = 命中题数 / 总题数。

三种模式并排跑（复用 retrieval.py 的开关），直接得出"每加一层涨多少"：
    vector : 只用①向量        （基线）
    hybrid : ①②③ 向量+BM25+RRF
    full   : ①②③④ 再加 Rerank

    python scripts/evaluate.py                    # 三种模式 × Pass@5/10/20
    python scripts/evaluate.py --mode full        # 只测一种
    python scripts/evaluate.py --k 5 10 20 30     # 自定义 k

无答案题（golden 为空）不计入 Pass@k —— 它们测的是幻觉防护（Step 8 接 LLM 后再用）。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import retrieval  # 同目录

EVAL_SET = Path("data/eval_set.jsonl")
DEFAULT_MODES = ["vector", "hybrid", "full"]
DEFAULT_KS = [5, 10, 20]


def load_eval_set(path: Path) -> list[dict]:
    rows = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    return rows


def pass_at_k(retrieved_keys: list[str], golden_keys: list[str], k: int) -> bool:
    """top-k 里是否含任一 golden chunk。"""
    topk = set(retrieved_keys[:k])
    return any(g in topk for g in golden_keys)


def evaluate(conn, client, questions: list[dict], mode: str, ks: list[int],
             max_k: int) -> dict:
    """对一种模式，一次检索 max_k 条，复用到所有 k 值上算 Pass@k。

    返回 {"all": {k: rate}, "en": {...}, "zh": {...}} —— 分语言统计，
    用来量化中文问英文语料的跨语言损耗。
    """
    hits_all = {k: 0 for k in ks}
    hits_lang = {"en": {k: 0 for k in ks}, "zh": {k: 0 for k in ks}}
    n_lang = {"en": 0, "zh": 0}

    for q in questions:
        lang = q.get("lang", "en")
        n_lang[lang] = n_lang.get(lang, 0) + 1
        hits = retrieval.retrieve(conn, client, q["question"], k=max_k, mode=mode)
        retrieved_keys = [h.chunk_key for h in hits]
        for k in ks:
            if pass_at_k(retrieved_keys, q["golden_chunk_keys"], k):
                hits_all[k] += 1
                hits_lang[lang][k] += 1

    n = len(questions)
    out = {"all": {k: hits_all[k] / n for k in ks}}
    for lang in ("en", "zh"):
        if n_lang[lang]:
            out[lang] = {k: hits_lang[lang][k] / n_lang[lang] for k in ks}
    out["_n"] = {"all": n, **n_lang}
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=DEFAULT_MODES, help="只测一种模式（默认三种都测）")
    p.add_argument("--k", type=int, nargs="+", default=DEFAULT_KS, dest="ks")
    p.add_argument("--eval-set", type=Path, default=EVAL_SET)
    args = p.parse_args()

    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not db or not key:
        raise SystemExit("需要 .env 里的 DATABASE_URL 和 OPENAI_API_KEY")

    from openai import OpenAI
    client = OpenAI(api_key=key)

    all_rows = load_eval_set(args.eval_set)
    answerable = [q for q in all_rows if q["golden_chunk_keys"]]
    no_answer = [q for q in all_rows if not q["golden_chunk_keys"]]

    print(f"评估集: {len(all_rows)} 题（有答案 {len(answerable)}，无答案 {len(no_answer)} 不计入 Pass@k）")
    print(f"k 值: {args.ks}")

    modes = [args.mode] if args.mode else DEFAULT_MODES
    max_k = max(args.ks)
    results: dict[str, dict] = {}

    with psycopg.connect(db) as conn:
        for mode in modes:
            print(f"\n跑 mode={mode} ...", flush=True)
            results[mode] = evaluate(conn, client, answerable, mode, args.ks, max_k)

    label = {"vector": "① 向量(基线)", "hybrid": "①②③ +BM25+RRF", "full": "①②③④ +Rerank"}
    n = results[modes[0]]["_n"]

    def table(subset: str, title: str):
        print(f"\n{'=' * 62}")
        print(f"{title}（{n[subset]} 题）")
        print(f"{'=' * 62}")
        print(f"{'模式':<20}" + "".join(f"Pass@{k:<7}" for k in args.ks))
        print("-" * 62)
        for mode in modes:
            if subset not in results[mode]:
                continue
            row = f"{label.get(mode, mode):<20}"
            for k in args.ks:
                row += f"{results[mode][subset][k] * 100:>6.1f}%  "
            print(row)
        print("=" * 62)

    # 总体
    table("all", "Pass@k 总体")

    # 分语言 —— 量化跨语言损耗
    table("en", "英文题")
    table("zh", "中文题")

    # 每加一层的增量（总体）
    if len(modes) > 1:
        print("\n增量（Pass@10，总体）:")
        order = [m for m in DEFAULT_MODES if m in results]
        for i in range(1, len(order)):
            prev, cur = order[i - 1], order[i]
            k = 10 if 10 in args.ks else args.ks[0]
            delta = (results[cur]["all"][k] - results[prev]["all"][k]) * 100
            print(f"  {label[prev]} → {label[cur]}: {delta:+.1f} pp")

    # 跨语言差距（full 模式）
    if "full" in results and "en" in results["full"] and "zh" in results["full"]:
        k = 10 if 10 in args.ks else args.ks[0]
        gap = (results["full"]["en"][k] - results["full"]["zh"][k]) * 100
        print(f"\n跨语言差距（full, Pass@{k}）: 英文 - 中文 = {gap:+.1f} pp")
        if gap > 5:
            print("  ⚠️ 中文明显偏低，考虑：扩展中文别名 / 调高中文时BM25权重 / 双语存储")


if __name__ == "__main__":
    main()
