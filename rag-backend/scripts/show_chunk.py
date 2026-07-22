"""按关键词或 chunk_key 查看 chunk 原文（只读）。

改数据之前先看清楚原文长什么样，不要凭印象改。

    python show_chunk.py GMAT                       # 正文里含 GMAT 的
    python show_chunk.py --key page:page_04:2       # 按 chunk_key 精确查
    python show_chunk.py GRE --full                 # 打印完整正文，不截断
"""
from __future__ import annotations

import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

APP_SCHEMA = "app"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("keyword", nargs="?", help="在 content/context 里搜这个词")
    p.add_argument("--key", help="按 chunk_key 精确查（可只给前缀）")
    p.add_argument("--full", action="store_true", help="打印完整正文，默认截断 600 字")
    args = p.parse_args()

    if not args.keyword and not args.key:
        p.error("给一个关键词，或用 --key 指定 chunk_key")

    load_dotenv()
    db = os.getenv("DATABASE_URL", "").strip()
    if not db:
        raise SystemExit("需要 .env 里的 DATABASE_URL")

    if args.key:
        where, params = "chunk_key like %s", (f"{args.key}%",)
    else:
        where = "(content ilike %s or context ilike %s)"
        params = (f"%{args.keyword}%", f"%{args.keyword}%")

    with psycopg.connect(db) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            select chunk_key, source_table, answer_type, conflict_group,
                   authoritative, context, content, metadata
            from {APP_SCHEMA}.document_chunks
            where {where}
            order by id
        """, params)
        rows = cur.fetchall()

    print(f"\n命中 {len(rows)} 条\n")
    for r in rows:
        print("=" * 78)
        print(f"chunk_key      {r['chunk_key']}")
        print(f"source_table   {r['source_table']}")
        print(f"answer_type    {r['answer_type']}")
        if r["conflict_group"]:
            mark = "✅ 以此为准" if r["authoritative"] else "❌ 非以此为准"
            print(f"conflict_group {r['conflict_group']}   {mark}")
        else:
            print("conflict_group （无）")

        md = r["metadata"]
        if isinstance(md, str):
            md = json.loads(md)
        if isinstance(md, dict) and md.get("source_url"):
            print(f"source_url     {md['source_url']}")

        if r["context"]:
            print(f"\n[context]\n{r['context']}")

        body = r["content"]
        if not args.full and len(body) > 600:
            body = body[:600] + f"\n... （还有 {len(r['content']) - 600} 字，加 --full 看全部）"
        print(f"\n[content]\n{body}\n")


if __name__ == "__main__":
    main()
