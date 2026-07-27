"""P3：用用户画像做个性化检索。

把 P2 抽取的画像（profile_extract.py 的输出格式）接进检索，让"选什么课""什么职业"
这类问题的答案贴合用户的目标方向。核心原则：

  只在"该个性化"时才个性化。问"学费/GMAT/截止日"这种客观事实，跟用户是谁无关，
  硬拼画像反而干扰检索——所以由数据自己判断：只有当问题检索到了 career_roles /
  courses / course_rules 这类"因人而异"的内容时，才启用个性化。

这一层不碰画像的存储（队友的 Redis / 云端库）——画像作为参数传进来即可，
不管它从哪来。字段就是 profile_extract.py 的输出，见 docs/user_profile_schema.md。
"""
from __future__ import annotations

import retrieval

# 命中这些表 = 这是一个"因人而异"的问题，值得个性化。
# 反之，programme_pages（学费/招生）、admissions_items（材料）这些是客观事实，不个性化。
PERSONALIZABLE_TABLES = {"career_roles", "courses", "course_rules"}

# target_role_std（role_id）-> 检索用的自然措辞。
# 用中文别名是有意的：语料里埋了技能的中文锚点（方案2），中文短语能同时命中
# career_roles 的英文原文和 courses 里的中文别名。
ROLE_PHRASES = {
    "quant_risk": "量化 风险建模 quantitative risk",
    "data_analytics": "数据分析 数据科学 machine learning",
    "fintech_pm": "金融科技产品经理 fintech product",
    "payments": "支付 区块链 数字资产 payments blockchain",
    "digital_banking": "数字银行 digital banking",
    "compliance_regtech": "合规 监管科技 compliance regtech",
}


def should_personalize(hits: list[retrieval.Hit], profile: dict | None,
                       top_n: int = 3) -> bool:
    """判断这个问题该不该个性化——由数据决定，不写死"哪些问题"的规则。

    条件：① 画像里有目标方向  ② 原始检索的前几条命中了 career/course 类内容。
    两者都满足才个性化。这样问学费/GMAT 时（命中的是 programme_pages/admissions），
    即便画像里有目标方向也不会去干扰。
    """
    if not profile or not profile.get("target_role_std"):
        return False
    return any(h.source_table in PERSONALIZABLE_TABLES for h in hits[:top_n])


def expand_query(question: str, profile: dict) -> str:
    """把目标方向拼进查询。用户只说"选什么课"，补成"量化…选什么课"。"""
    role = profile.get("target_role_std")
    phrase = ROLE_PHRASES.get(role, role or "")
    return f"{phrase} {question}".strip()


def profile_brief(profile: dict | None) -> str:
    """给 LLM 的一句话画像摘要，让回答语气贴合。只挑对回答有用的字段，英文写（跟 prompt 一致）。

    返回空串表示没有可用画像 —— 调用方据此决定要不要把这段塞进 prompt。
    """
    if not profile:
        return ""
    bits = []

    stage = profile.get("lifecycle_stage")
    if stage:
        bits.append(f"stage={stage}")

    bg = (profile.get("academic_background") or {}).get("std")
    if bg:
        bits.append(f"background={bg}")

    tech = (profile.get("tech_level") or {}).get("std")
    if tech:
        bits.append(f"tech_level={tech}")

    role = profile.get("target_role_std")
    if role:
        bits.append(f"target_role={role}")

    # 届别对培养方案很关键（course_rules 分届），带上
    if profile.get("intake_year"):
        bits.append(f"intake_year={profile['intake_year']}")

    return "; ".join(bits)


def personalize(conn, oa_client, question: str, hits: list[retrieval.Hit],
                profile: dict | None, k: int, mode: str) -> tuple[list[retrieval.Hit], bool]:
    """P3 主入口。给定原始检索结果，决定要不要重检索。

    返回 (最终 hits, 是否个性化了)。
    两趟检索：先按原问题检索（调用方已做），若判定该个性化，则用扩展查询再检索一次，
    用新结果替换。不该个性化就原样返回——多数客观事实问题走这条，零额外开销。
    """
    if not should_personalize(hits, profile):
        return hits, False
    expanded = expand_query(question, profile)
    new_hits = retrieval.retrieve(conn, oa_client, expanded, k=k, mode=mode)
    return new_hits, True
