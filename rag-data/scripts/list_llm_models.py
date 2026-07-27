"""列出 LLM 端点上实际可用的模型（排查 404: model not found）。

NVIDIA build 页面上展示的模型很多，但账号能调的不一定是页面上写的那个 ID。
OpenAI 兼容接口都提供 GET /v1/models，直接问它要准确的名字。

    python list_llm_models.py            # 只列含 deepseek 的
    python list_llm_models.py --all      # 全部列出来
"""
from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--all", action="store_true", help="列出全部模型，不只 deepseek")
    p.add_argument("--filter", default="deepseek", help="按关键字过滤（默认 deepseek）")
    args = p.parse_args()

    load_dotenv()
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        raise SystemExit("需要 .env 里的 NVIDIA_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=key)

    print(f"端点：{base_url}\n")
    ids = sorted(m.id for m in client.models.list().data)
    print(f"账号可用模型共 {len(ids)} 个\n")

    shown = ids if args.all else [i for i in ids if args.filter.lower() in i.lower()]
    if not shown:
        print(f"⚠️ 没有含 '{args.filter}' 的模型。用 --all 看全部。")
    else:
        title = "全部模型" if args.all else f"含 '{args.filter}' 的模型"
        print(f"{title}：")
        for i in shown:
            print(f"  {i}")

    print("\n把要用的那个写进 .env 的 LLM_MODEL")


if __name__ == "__main__":
    main()
