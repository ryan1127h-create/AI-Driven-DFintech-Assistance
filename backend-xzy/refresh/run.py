"""CLI for the refresh pipeline.

    python -m refresh.run module_catalog        # fetch + decide (auto/queue)
    python -m refresh.run --list-pending
    python -m refresh.run --approve <file> --admin alice
"""
from __future__ import annotations

import argparse
import json
import sys

from . import pending, pipeline
from .sources import all_source_names, live_fetcher_for


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="分级刷新管线")
    p.add_argument("source", nargs="?", choices=all_source_names())
    p.add_argument("--live", action="store_true", help="use the real network fetcher (e.g. NUSMods)")
    p.add_argument("--list-pending", action="store_true")
    p.add_argument("--approve", metavar="PENDING_FILE")
    p.add_argument("--admin", default="reviewer")
    args = p.parse_args(argv)

    if args.list_pending:
        items = pending.list_pending()
        if not items:
            print("待审队列为空。")
        for it in items:
            print(f"- {it['file']}\n    源: {it['source']} | 原因: {', '.join(it['reasons'])} | {it['created']}")
        return 0

    if args.approve:
        res = pipeline.approve_pending(args.approve, admin=args.admin)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["status"] == "approved" else 1

    if not args.source:
        print("用法: python -m refresh.run <source> | --list-pending | --approve <file>")
        print("可用 source:", ", ".join(all_source_names()))
        return 0

    fetcher = live_fetcher_for(args.source) if args.live else None
    if args.live:
        print(f"[live] 正在从真实源抓取 {args.source} ...")
    res = pipeline.run(args.source, fetcher=fetcher, admin="refresh-bot")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
