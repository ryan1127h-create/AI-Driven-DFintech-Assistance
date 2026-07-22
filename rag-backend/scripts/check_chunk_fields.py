"""体检 document_chunks 的三个"回答层"字段有没有值。

Step 8 要用到 answer_type / conflict_group / authoritative / metadata.source_url，
但这些字段是切片时写的，可能是空的。动手写 answer.py 之前先确认。

只读，不改任何数据。

    python scripts/check_chunk_fields.py
"""
from __future__ import annotations

import json
import os
from collections import Counter

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

APP_SCHEMA = "app"


def main() -> None:
    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    if not db:
        raise SystemExit("需要 .env 里的 DATABASE_URL")

    with psycopg.connect(db) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select chunk_key, source_table, answer_type,
                   conflict_group, authoritative, metadata
            from {APP_SCHEMA}.document_chunks
            order by id
        """)
        rows = cur.fetchall()

    print(f"\n总计 {len(rows)} 条 chunk\n")

    # --- embedding 体检（原 test_search.py 的 health_check，该脚本已删）---
    # 重跑切片后如果某条 embedding 写失败，向量检索会静默漏掉它——不报错，
    # 只是永远检索不到。所以每次改完数据都该查一遍。
    print("=" * 60)
    print("embedding 体检")
    print("=" * 60)
    with psycopg.connect(db) as conn, conn.cursor() as cur:
        cur.execute(f"""
            select count(*) filter (where embedding is null),
                   count(distinct vector_dims(embedding)),
                   min(vector_dims(embedding))
            from {APP_SCHEMA}.document_chunks
        """)
        missing, dim_kinds, dim = cur.fetchone()

    print(f"  embedding 为空： {missing} 条  {'✅' if missing == 0 else '❌ 这些 chunk 永远检索不到'}")
    if dim_kinds == 1:
        print(f"  向量维度：      {dim}  {'✅' if dim == 1536 else '⚠️ 与 text-embedding-3-small 的 1536 不符'}")
    else:
        print(f"  ❌ 维度不统一：库里存在 {dim_kinds} 种不同维度，说明混用了不同 embedding 模型")
    print()

    # --- answer_type ---
    print("=" * 60)
    print("answer_type 分布")
    print("=" * 60)
    for val, n in Counter(r["answer_type"] for r in rows).most_common():
        print(f"  {str(val):<20} {n:>4} 条")

    # 按来源表交叉看，确认 official/advisory 是不是按数据源分的
    print("\n  按 source_table 交叉：")
    cross = Counter((r["source_table"], r["answer_type"]) for r in rows)
    for (table, at), n in sorted(cross.items()):
        print(f"    {table:<22} {str(at):<12} {n:>4} 条")

    # --- conflict_group / authoritative ---
    print("\n" + "=" * 60)
    print("conflict_group / authoritative")
    print("=" * 60)
    conflicts = [r for r in rows if r["conflict_group"]]
    if not conflicts:
        print("  ⚠️ 没有任何 chunk 标了 conflict_group（GMAT 冲突组没入库？）")
    else:
        for r in conflicts:
            flag = "✅权威" if r["authoritative"] else "  非权威"
            print(f"  [{r['conflict_group']}] {flag}  {r['chunk_key']}")

    n_auth = sum(1 for r in rows if r["authoritative"])
    print(f"\n  authoritative=true 共 {n_auth} 条")

    # --- metadata：source_url 到底叫什么名字 ---
    print("\n" + "=" * 60)
    print("metadata 的 key（Step 8-3 要从这里取来源链接）")
    print("=" * 60)
    keys = Counter()
    for r in rows:
        md = r["metadata"]
        if isinstance(md, str):          # 万一存成了 json 字符串
            md = json.loads(md)
        if isinstance(md, dict):
            keys.update(md.keys())
    if not keys:
        print("  ⚠️ metadata 全空")
    for key, n in keys.most_common():
        print(f"  {key:<24} 出现 {n:>4} 次")

    # 有 url 的 key 抽样看看长什么样
    print("\n  含 url 的字段抽样：")
    shown = 0
    for r in rows:
        md = r["metadata"]
        if isinstance(md, str):
            md = json.loads(md)
        if not isinstance(md, dict):
            continue
        for key, val in md.items():
            if "url" in key.lower() and val:
                print(f"    {r['chunk_key']:<28} {key} = {val}")
                shown += 1
                break
        if shown >= 5:
            break
    if shown == 0:
        print("    ⚠️ 没找到任何含 url 的字段 —— 8-3 来源引用需要先补数据")

    # --- source_url 按表统计覆盖率（Step 8-3 要靠它给出处）---
    print("\n" + "=" * 60)
    print("source_url 覆盖率（按来源表）")
    print("=" * 60)
    per_table: dict[str, list[int]] = {}
    for r in rows:
        md = r["metadata"]
        if isinstance(md, str):
            md = json.loads(md)
        has = bool(isinstance(md, dict) and md.get("source_url"))
        stat = per_table.setdefault(r["source_table"], [0, 0])
        stat[0] += 1
        stat[1] += 1 if has else 0

    for table, (total, has) in sorted(per_table.items()):
        mark = "✅" if has == total else ("❌" if has == 0 else "⚠️")
        print(f"  {mark} {table:<32} {has:>3}/{total:<3} 条有 source_url")

    # --- 有多少 chunk 缺关键字段 ---
    print("\n" + "=" * 60)
    print("缺字段的 chunk")
    print("=" * 60)
    missing_at = [r["chunk_key"] for r in rows if not r["answer_type"]]
    print(f"  answer_type 为空： {len(missing_at)} 条")
    for k in missing_at[:10]:
        print(f"    - {k}")
    if len(missing_at) > 10:
        print(f"    ...还有 {len(missing_at) - 10} 条")

    print()


if __name__ == "__main__":
    main()
