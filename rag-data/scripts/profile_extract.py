"""P2：从用户对话里抽取结构化画像。

把用户说的大白话（"我双非金融，GMAT680，想做量化"）抽成规范 JSON，供队友的
Redis 长期记忆模块存储、供 P3 个性化检索使用。字段定义见 docs/user_profile_schema.md。

设计要点：
  · 保守抽取——拿不准的字段一律 null，绝不猜测（没提 GMAT 就不填，不能编分数）
  · 数字原样——GMAT/GRE/语言分照抄，不换算不改写
  · target_role_std 只能取 6 个 career_roles 之一，映射不出就 null（保证对得上检索库）
  · lifecycle_stage 只在用户"明说"身份时填，不从"问了什么话题"去猜（会错得离谱）
  · 输出严格 JSON，走同一个 DeepSeek V4 Pro，temperature=0

这一步只负责"抽取"，不负责"存储"（队友）也不负责"检索"（P3）。

用法：
    python profile_extract.py "我双非金融本科，考了GMAT680，想做量化风险"
    python profile_extract.py "I'm an admitted student starting in 2026, TOEFL 100"
    echo "..." | python profile_extract.py -        # 从 stdin 读

⚠️ 要在 scripts/ 目录下跑（和 answer.py 一样依赖 .env）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

# 复用 answer.py 里已验证的模型/端点配置，保持一致
LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_LLM_MODEL = "deepseek-ai/deepseek-v4-pro"
TEMPERATURE = 0
MAX_TOKENS = 512          # 画像 JSON 很短
THINKING = False

# 瞬时失败重试（NVIDIA 端点首次调用可能冷启动 404），同 answer.py
MAX_RETRIES = 4
RETRY_BASE_WAIT = 2

# target_role_std 的合法取值——必须与 career_roles 表一致（见 docs/user_profile_schema.md §三）。
# 抽取只能从这里选，选不出填 null，从而保证画像里的方向一定对得上检索库。
CAREER_ROLES = [
    "quant_risk",          # Quantitative / Risk Analyst
    "data_analytics",      # Financial Data Science / AI
    "fintech_pm",          # FinTech Product Manager
    "payments",            # Payments / Blockchain / Digital Assets
    "digital_banking",     # Digital Banking
    "compliance_regtech",  # Compliance / RegTech
]

# admitted = 拿到 offer 但还没入学；enrolled = 已在读。两者是不同用户群（PDF 用户分组），
# 且都对应"填 intake_year"，但需求和阶段不同，必须分开。
LIFECYCLE_STAGES = ["prospect", "applicant", "admitted", "enrolled", "alumni"]
TECH_LEVELS = ["none", "basic", "strong"]

# 空画像模板——抽取失败或字段缺失时的兜底形状，保证输出结构永远一致
EMPTY_PROFILE = {
    "lifecycle_stage": None,
    "academic_background": {"raw": None, "std": None},
    "tech_level": {"raw": None, "std": None},
    "gmat": None,
    "gre": None,
    "toefl": None,
    "ielts": None,
    "target_role_raw": None,
    "target_role_std": None,
    "application_term": None,
    "intake_year": None,
}


SYSTEM_PROMPT = f"""You extract a structured applicant profile from what a user says to \
an NUS MSc Digital Financial Technology admissions assistant. Output ONLY a JSON object, \
no prose, no markdown fences.

Be conservative: only fill a field if the user actually stated or clearly implied it. \
If something is not mentioned, leave it null. NEVER guess a value. It is correct and \
expected for most fields to be null.

Fields (output exactly these keys):

- "lifecycle_stage": one of {LIFECYCLE_STAGES}, or null. Meanings:
    · "prospect"  — still exploring, hasn't applied
    · "applicant" — has applied / is applying, no decision yet
    · "admitted"  — received an offer but NOT yet started classes ("I got admitted / \
I've been accepted / 我被录取了 / 我拿到offer了")
    · "enrolled"  — a current student, already taking classes ("我在读 / I'm a current student")
    · "alumni"    — has graduated
  ONLY set this if the user explicitly states their stage. "被录取/admitted/accepted" -> \
"admitted", NOT "enrolled". Do NOT infer stage from the topic they ask about — asking \
about tuition or courses does NOT tell you their stage. If unstated, null.

- "academic_background": {{"raw": <user's own words or null>, "std": <one lowercase \
English keyword like "finance", "computer_science", "economics", or null>}}.

- "tech_level": {{"raw": <user's words or null>, "std": one of {TECH_LEVELS} or null}}. \
"none"=no programming/math, "basic"=some, "strong"=solid coding/quant background.

- "gmat", "gre", "toefl", "ielts": integer scores exactly as stated, else null. \
Copy digits verbatim; never convert between them.

- "target_role_raw": the user's own words for their target career, or null.
- "target_role_std": map the target career to EXACTLY ONE of {CAREER_ROLES}, or null if \
it doesn't clearly map. Mapping hints: quant/risk->quant_risk, data/AI/ML->data_analytics, \
product/PM->fintech_pm, payments/blockchain/crypto->payments, digital banking->\
digital_banking, compliance/regulation->compliance_regtech.

- "application_term": e.g. "2026 Fall", only if stage is prospect/applicant and stated, \
else null.
- "intake_year": one of "2025"/"2026"/"2027", only if the user is admitted/enrolled and \
stated it, else null.

Reply in JSON only."""


def _client_and_model():
    load_dotenv()
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        raise SystemExit("需要 .env 里的 NVIDIA_API_KEY")
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL
    base_url = os.getenv("LLM_BASE_URL", "").strip() or LLM_BASE_URL
    from openai import OpenAI
    # 设 60s 超时：NVIDIA 免费通道偶尔某个模型无响应，宁可快速失败重试/报错，
    # 也不要像之前那样干等 90 秒不知道发生了什么
    return OpenAI(base_url=base_url, api_key=key, timeout=60), model


def _call_llm(client, model: str, text: str) -> str:
    """调 LLM，失败重试（NVIDIA 首次调用冷启动 404，同 answer.py 的处理）。"""
    import time
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
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
                wait = RETRY_BASE_WAIT * (2 ** attempt)
                print(f"    ⚠️ 第 {attempt + 1} 次调用失败（{type(e).__name__}），{wait}s 后重试",
                      file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError(f"调用 LLM 连续失败 {MAX_RETRIES} 次：{last_err}") from last_err


def _parse_json(raw: str) -> dict:
    """从 LLM 输出里抠出 JSON。即便叮嘱过，模型偶尔仍会包 ```json 或加话，容错处理。"""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"输出里找不到 JSON：{raw[:200]}")
    return json.loads(s[start:end + 1])


def _sanitize(data: dict) -> dict:
    """把 LLM 输出规整到固定形状 + 校验枚举值。

    LLM 大体听话，但不能全信：枚举值可能拼错、数字可能给成字符串、可能多/少字段。
    这里做最后一道防线，保证交给下游（Redis / 检索）的画像结构和取值永远合法。
    """
    out = json.loads(json.dumps(EMPTY_PROFILE))  # 深拷贝模板

    def as_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def as_half(v):
        # 雅思是 0.5 一档（6.0/6.5/7.0…），必须用 float，不能像其它成绩那样砍成整数
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def enum_or_none(v, allowed):
        return v if v in allowed else None

    if isinstance(data.get("lifecycle_stage"), str):
        out["lifecycle_stage"] = enum_or_none(data["lifecycle_stage"], LIFECYCLE_STAGES)

    for field in ("academic_background", "tech_level"):
        v = data.get(field)
        if isinstance(v, dict):
            out[field]["raw"] = v.get("raw") or None
            out[field]["std"] = v.get("std") or None
    # tech_level.std 必须是合法枚举
    out["tech_level"]["std"] = enum_or_none(out["tech_level"]["std"], TECH_LEVELS)

    for field in ("gmat", "gre", "toefl"):   # 这三个都是整数分
        out[field] = as_int(data.get(field))
    out["ielts"] = as_half(data.get("ielts"))  # 雅思是 0.5 档的小数

    out["target_role_raw"] = data.get("target_role_raw") or None
    out["target_role_std"] = enum_or_none(data.get("target_role_std"), CAREER_ROLES)

    out["application_term"] = data.get("application_term") or None
    iy = data.get("intake_year")
    out["intake_year"] = str(iy) if str(iy) in ("2025", "2026", "2027") else None

    return out


def extract_profile(client, model: str, text: str) -> dict:
    """对外主入口：一段用户文本 -> 规范画像 dict。"""
    raw = _call_llm(client, model, text)
    return _sanitize(_parse_json(raw))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text", help="用户说的话；传 - 从 stdin 读")
    args = p.parse_args()

    text = sys.stdin.read() if args.text == "-" else args.text
    text = text.strip()
    if not text:
        raise SystemExit("没有输入文本")

    client, model = _client_and_model()
    profile = extract_profile(client, model, text)
    print(json.dumps(profile, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
