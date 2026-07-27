"""校准检索置信度阈值：找出"有答案 vs 无答案"的分界线。

背景：整合到 xzy 后端时，他的置信门控靠检索 score 判断 转人工/追问/回答
(§0.2: <0.60 转人工…)。但那套阈值是按他的 BM25 校准的，换我们的四层检索后
score 语义变了，必须重新找线。

方法：跑 eval_set 65 题(60 有答案 + 5 无答案)，记录每题 top1 score。
  · 无答案题的分数 → 应该低(该判"没有")
  · 有答案题的分数 → 应该高(该判"能答")
  · 若两组分得开，中间就是阈值；分不开则说明 rerank 分不适合当门控信号。

分数存进 data/calibration_scores.json，调阈值时读存档不重跑(65 题 Cohere 限流
约 7-8 分钟)。加 --analyze 只读存档做分析、不重跑。

    python calibrate_threshold.py            # 跑检索 + 分析
    python calibrate_threshold.py --analyze  # 只分析已存的分数
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import retrieval

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCORES_PATH = DATA_DIR / "calibration_scores.json"


def _is_no_answer(row: dict) -> bool:
    return not (row.get("golden_chunk_keys") or [])


def run_retrieval() -> list[dict]:
    """跑 65 题，记录每题 top1 的 rerank score 和检索命中。"""
    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    oa_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not db or not oa_key:
        raise SystemExit("需要 .env 里的 DATABASE_URL 和 OPENAI_API_KEY")
    from openai import OpenAI
    oa = OpenAI(api_key=oa_key)

    rows = [json.loads(l) for l in (DATA_DIR / "eval_set.jsonl").open(encoding="utf-8") if l.strip()]
    n = len(rows)
    print(f"跑 {n} 题(Cohere 限流 6.5s/题，约 {n * 7 // 60} 分钟)…\n")

    out = []
    with psycopg.connect(db) as conn:
        for i, r in enumerate(rows, 1):
            hits = retrieval.retrieve(conn, oa, r["question"], k=5, mode="full")
            top1 = hits[0].score if hits else 0.0
            out.append({
                "q_id": r.get("q_id"),
                "question": r["question"],
                "no_answer": _is_no_answer(r),
                "top1_score": round(float(top1), 4),
                "top1_key": hits[0].chunk_key if hits else None,
                "lang": r.get("lang"),
            })
            flag = "无答案" if _is_no_answer(r) else "有答案"
            print(f"  [{i:2d}/{n}] {flag}  {top1:.4f}  {r.get('q_id')}  {r['question'][:40]}")

    SCORES_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n分数已存 → {SCORES_PATH}")
    return out


def analyze(scores: list[dict]) -> None:
    ans = sorted((s["top1_score"] for s in scores if not s["no_answer"]))
    noans = sorted((s["top1_score"] for s in scores if s["no_answer"]))

    print("\n" + "=" * 66)
    print("分数分布")
    print("=" * 66)

    def stat(name, xs):
        if not xs:
            print(f"  {name}: (无)")
            return
        mid = xs[len(xs) // 2]
        print(f"  {name}({len(xs)}题): 最低 {xs[0]:.4f}  中位 {mid:.4f}  最高 {xs[-1]:.4f}")

    stat("有答案", ans)
    stat("无答案", noans)

    # 无答案题逐条列出(整合门控最关心：这些该被判"没有")
    print("\n  无答案题的分数(该低于阈值):")
    for s in sorted((s for s in scores if s["no_answer"]), key=lambda s: s["top1_score"]):
        print(f"    {s['top1_score']:.4f}  {s['q_id']}  {s['question'][:44]}")

    # 能不能分开？
    print("\n" + "=" * 66)
    print("能否用一条线分开")
    print("=" * 66)
    if not ans or not noans:
        print("  数据不足。")
        return
    noans_max = noans[-1]          # 无答案题的最高分
    ans_min = ans[0]              # 有答案题的最低分
    print(f"  无答案题最高分: {noans_max:.4f}")
    print(f"  有答案题最低分: {ans_min:.4f}")
    if ans_min > noans_max:
        thr = round((ans_min + noans_max) / 2, 4)
        print(f"  ✅ 两组完全分开！建议阈值 = {thr}")
        print(f"     (低于 {thr} 判'没有/转人工'，高于则'可答')")
    else:
        # 有重叠——找一个漏答/误答最少的阈值
        overlap = [s for s in scores if noans_max >= s["top1_score"] >= ans_min]
        print(f"  ⚠️ 两组有重叠(重叠区 {ans_min:.4f} ~ {noans_max:.4f}，{len(overlap)} 题)")
        print("     rerank 分数无法干净地区分有/无答案。")
        # 扫描候选阈值，报告每个的漏答(把有答案判没)和误答(把无答案判有)
        cands = sorted({round(s["top1_score"], 3) for s in scores})
        print("\n     阈值扫描(漏答=该答却判没有; 误答=没答案却放行):")
        print("     阈值      漏答/60   误答/5")
        best = None
        for t in cands:
            miss = sum(1 for x in ans if x < t)        # 有答案但低于阈值 → 漏答
            wrong = sum(1 for x in noans if x >= t)    # 无答案但高于阈值 → 误答(会瞎编)
            cost = miss + wrong * 3                     # 误答(幻觉)代价更高，加权
            if best is None or cost < best[0]:
                best = (cost, t, miss, wrong)
            if t in (cands[0], cands[-1]) or wrong <= 1 or miss <= 3:
                print(f"     {t:.3f}     {miss:>2}        {wrong}")
        print(f"\n     折中最优阈值 ≈ {best[1]:.3f}(漏答 {best[2]}/60，误答 {best[3]}/5)")

    print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--analyze", action="store_true", help="只读已存分数做分析，不重跑检索")
    args = p.parse_args()

    if args.analyze:
        if not SCORES_PATH.exists():
            raise SystemExit(f"没有存档 {SCORES_PATH}，先不带 --analyze 跑一次")
        scores = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    else:
        scores = run_retrieval()
    analyze(scores)


if __name__ == "__main__":
    main()
