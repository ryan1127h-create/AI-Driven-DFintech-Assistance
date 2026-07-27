"""排查 404：把变量一个个隔离，找出到底哪个参数触发的。

模型名已确认在 /v1/models 列表里，所以 404 不是名字拼错。剩下的嫌疑：
  - extra_body 的 chat_template_kwargs（NVIDIA 页面示例给的，不一定所有模型都收）
  - 模型虽然列出来了，但账号实际没开通（NVIDIA 也可能返回 404）

每种组合发一个最小请求（max_tokens=16，几乎不消耗配额），打印成功或完整错误。

    python diagnose_llm.py
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

# 从最简单的组合开始，逐个加参数——第一个失败的就是元凶
CASES = [
    ("v4-pro   最小请求（不带任何额外参数）", "deepseek-ai/deepseek-v4-pro", {}),
    ("v4-pro   + temperature/max_tokens", "deepseek-ai/deepseek-v4-pro",
     {"temperature": 0, "max_tokens": 16}),
    ("v4-pro   + extra_body(thinking)", "deepseek-ai/deepseek-v4-pro",
     {"temperature": 0, "max_tokens": 16,
      "extra_body": {"chat_template_kwargs": {"thinking": False}}}),
    ("v4-flash 最小请求", "deepseek-ai/deepseek-v4-flash", {}),
    ("v4-flash + extra_body(thinking)", "deepseek-ai/deepseek-v4-flash",
     {"temperature": 0, "max_tokens": 16,
      "extra_body": {"chat_template_kwargs": {"thinking": False}}}),
]


def main() -> None:
    load_dotenv()
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        raise SystemExit("需要 .env 里的 NVIDIA_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=key)

    print(f"端点：{base_url}\n")
    ok = []
    for label, model, kwargs in CASES:
        print(f"[测试] {label}")
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say OK."}],
                **({"max_tokens": 16} | kwargs),
            )
            text = (resp.choices[0].message.content or "").strip()
            print(f"   ✅ 成功 → {text[:60]!r}\n")
            ok.append((model, kwargs))
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {e}")
            # 404/400 的响应体里常带真正的原因，SDK 把它放在 .body
            body = getattr(e, "body", None)
            if body:
                print(f"      响应体：{body}")
            print()

    print("=" * 70)
    if not ok:
        print("全部失败 —— 大概率是账号没开通这些模型，或端点地址不对。")
    else:
        model, kwargs = ok[0]
        print(f"可用的最简组合：model={model}")
        print(f"参数：{kwargs or '（无额外参数）'}")
        print("\n把它写进 .env 的 LLM_MODEL；如果 extra_body 那一档失败，")
        print("就把 answer.py 里的 THINKING 相关参数去掉。")
    print("=" * 70)


if __name__ == "__main__":
    main()
