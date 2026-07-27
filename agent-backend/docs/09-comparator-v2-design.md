# Technical Design — Comparator v2 (#6 深化)

> **v3 起(2026-06-08)被取代/补充**:数据与输出升级为三态 cell(`verified`/`unknown`/`synthesis`)+ facts/synthesis 分区 + 确定性防排名护栏,展示维度扩到 11(含 PDF 4 维)。见 [v3 spec](superpowers/specs/2026-06-08-comparator-fact-synthesis-design.md) 与 [v3 plan](superpowers/plans/2026-06-08-comparator-fact-synthesis.md)。本文档描述的 v2 加权评分(role_fit/cost/duration)在 v3 中**不变**。
> **状态**:草案 · 已确认 · 合规约束不变(disclaimer、不生成排名词、每项带来源)
> 四项整合:① 多接学校 ② 加可对比维度 ③ role_strengths 可辨护化 ④ 按用户优先级加权。

## 1. 数据 v2(真实、带来源,经 trusted=false 强制审核入库)
- **5 所真实项目**:NUS DFT(target)、SMU Applied Finance(FinTech track)、NTU MSc FinTech、**SMU MITB(FinTech & Analytics)**、**HKUST MSc FinTech**。
- **维度扩为 7**:`curriculum_focus, duration, format, fees, intake, scholarship, gmat_gre`。缺数据一律如实写"未公开,请以官方为准"。
- `role_strengths` 不再写死在数据里(改由引擎推导,见 §3)。

## 2. role_strengths 可辨护化(`engine.derive_role_strengths`)
- `_ROLE_KEYWORDS`:每个目标岗位一组中英关键词。
- 对每个项目的 `curriculum_focus` 文本做关键词匹配 → 命中的岗位即该项目"擅长方向",并记录**命中的词**作为理由(`role_reasons`)。
- fit 打分改用推导结果(替代人工 role_strengths),输出 `matched_roles` + `role_reasons`。

## 3. 加权评分(`engine.score_programs`)
确定性评分,每项 0~1:
- `role_fit` = 推导命中的目标岗位数 / 用户目标岗位数。
- `cost` = 解析最低学费(HK$ 按固定汇率≈0.17 折 SGD,标注近似;"未公开"→中性 0.5)→ 越低分越高(min-max 归一)。
- `duration` = 解析最短月数("年"/"个月"/区间取下界;未知→中性)→ 越短分越高。

**用户权重**经 `slots.priorities`(如 `{cost:0.6, role_fit:0.4}`,自动归一);默认 `{role_fit:1.0}`。
`weighted_score = Σ wᵢ·scoreᵢ`;`best_for_you` = 最高加权分(并列偏向 target)。输出每校 `weighted_score` + `score_breakdown`。

## 4. Agent / 渲染
- `compare(target_roles, priorities)`;agent 从 `slots.priorities` 取权重。
- rows 增加:`matched_roles`、`role_reasons`、`weighted_score`、`score_breakdown`,以及 7 维 `values`。
- `narrative` 仍只基于事实、无排名词;`best_for_you` 解释绑定加权依据。
- 学生页:显示加权分 + 更多维度 + 来源链接。

## 5. 验证
role 推导(命中/理由)、各评分函数(cost/duration 解析、未知中性)、加权排序与权重归一、新 schema 7 维齐全、refresh 强制审核;全离线确定性 + 回归。
