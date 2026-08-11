# 成员B 三个业务模块：接口契约与代码导读

面向：前端对接、成员A（路由注册）、以及想读懂代码的组员。
三个模块：课程推荐 `course_recommendation`、项目比较 `program_comparison`、职业规划 `career_planning`。

统一设计：

- 调用链永远是一条直线：`api.py → service.py → repository.py / agents/ → 返回`。
- 所有数字、筛选、排序由代码计算（可复现、可测试）；AI 只做「选择与表达」，且每一步 AI 失败都有纯代码兜底，接口不会因 AI 挂掉而 500。
- 全部只读数据库；跨模块只通过对方 `interface.py`。
- 用户身份暂用 `TEST_USER_ID` 占位（等登录体系）；所有函数已预留 `user_id` 参数。

路由注册（成员A，在 `app/api/v1/router.py` 加三行）：

```python
from app.modules.course_recommendation import api as course_api
from app.modules.program_comparison import api as comparison_api
from app.modules.career_planning import api as career_api

router.include_router(course_api.router,     tags=["course_recommendation"])  # POST /course-recommendations
router.include_router(comparison_api.router, tags=["program_comparison"])     # POST /program-comparisons
router.include_router(career_api.router,     tags=["career_planning"])        # POST /career-plans
```

---

## 1. POST /api/v1/course-recommendations 课程推荐

请求（三个字段都可不填）：

```json
{
  "target_role": "fintech_pm",
  "completed_courses": ["FT5005", "IT5001X"],
  "preferences": ["digital banking", "product"]
}
```

- `target_role`：6 个标准职业 id（`quant_risk` / `data_analytics` / `fintech_pm` / `payments` / `digital_banking` / `compliance_regtech`）或**任意自由文本**（如 "blockchain developer"，由 AI 映射到技能标签，响应 notes 会注明）。不填→自动用画像里的 `target_role_std`。
- `completed_courses`：已修课程代码。不填→自动读画像的 `completed_courses` 字段（notes 会注明）。画像里简历抽出的**课程名**（非课号，如 "Machine Learning"）无法匹配 NUS 课程目录，会进入 `completed_unrecognized` 明示，不会被静默丢弃。
- `preferences`：兴趣关键词，用于匹配课程简介。

响应要点：

```json
{
  "target_role": "FinTech Product Manager",
  "recommended_courses": [
    {"course_code": "FT5007", "course_title": "...", "units": 12,
     "section": "Capstone Project", "priority": "high",
     "matched_skills": ["product", "finance"], "reason": "..."}
  ],
  "skill_gaps": ["product"],
  "completed_recognized": ["FT5005"],
  "completed_unrecognized": ["XX999"],
  "completed_units": 4,
  "notes": ["..."],
  "sources": ["..."]
}
```

代码分工：硬性过滤（排除已修 / preclusion 冲突 / 不可推荐课，算学分和技能缺口）→ 生成候选池，全是代码（`agents/rule_engine.py`）；AI 从池里挑 6-8 门、定优先级、写理由（`agents/recommendation_agent.py`），代码校验 AI 选的课必须在池内，编造的课号直接丢弃；AI 失败→规则打分兜底。

## 2. 项目比较

### GET /api/v1/program-comparisons/options 表单选项

无参数。返回可比较的项目全名列表和支持的维度，**前端请用它渲染下拉框/多选框，不要做自由文本输入**——这样用户永远选不到我们没有数据的学校：

```json
{"programs": ["NUS MSc Digital Financial Technology", "..."],
 "dimensions": ["curriculum", "fees", "admission"]}
```

### POST /api/v1/program-comparisons 执行比较

请求（都可不填）：

```json
{
  "programs": ["NTU", "HKUST"],
  "focus": ["curriculum", "fees", "admission"],
  "target_role": "fintech_pm"
}
```

- `programs`：模糊匹配（"NTU" 即可）。不填→NUS + 全部 4 个竞品（NTU、HKUST、SMU MAF、SMU MITB）。NUS 永远作为基准列。
- `focus`：维度。`career` 可传，但知识库暂无就业数据，会以 notes 说明。
- `target_role`：影响匹配度的技能项。不填→用画像。

响应要点：

```json
{
  "programs": ["NUS MSc Digital Financial Technology", "..."],
  "comparison_table": [{"dimension": "fees", "values": {"NUS ...": "单元格文本"}}],
  "match_scores": [
    {"program": "...", "total": 75,
     "subscores": [{"name": "skill_focus", "weight": 0.5, "score": 80,
                    "included": true, "evidence": "命中说明"}]}
  ],
  "program_comments": {"NUS ...": "针对你个人情况的适配点评"},
  "best_fit_summary": "中性总结",
  "notes": ["..."], "sources": ["各校官网链接"]
}
```

匹配度（0-100，纯代码算）：技能重点匹配 50% + 标化考试门槛 30% + 在职灵活度 20%；某项数据不足就**不计入**并按剩余权重归一（`included: false`，`evidence` 说明缺什么）；全缺→`total: null`。这是「和你个人的匹配参考」，不是项目排名。AI 只压缩表格文字（数字必须原样）、写点评和总结；失败→单元格显示原文。

## 3. POST /api/v1/career-plans 职业规划

请求（都可不填）：

```json
{"target_role": "quant_risk", "timeline": "12 months", "region": "Singapore"}
```

响应要点：

```json
{
  "target_role": "Quantitative / Risk Analyst",
  "current_fit": "现状评估（2-4 句）",
  "skill_gaps": ["risk_modeling"],
  "recommended_courses": [{"course_code": "BMD5301", "course_title": "...",
                           "priority": "high", "reason": "..."}],
  "short_term_actions": ["近 6 个月行动"],
  "medium_term_actions": ["之后的行动"],
  "notes": ["..."], "sources": ["..."]
}
```

技能缺口和课程完全来自课程推荐模块（同一份实现，不重复计算）；AI 只写叙述文字（现状、行动建议），全程 advisory 措辞、不承诺就业结果；失败→模板兜底。

---

## 代码导读（每个文件干什么）

以 `course_recommendation` 为例（另两个模块结构相同）：

| 文件 | 干什么 | 有没有 AI |
|---|---|---|
| `api.py` | 收请求、转给 service、包装响应；出错返回通用 500（详情只进服务端日志） | 无 |
| `schemas.py` | 定义请求/响应 JSON 的形状和长度限制 | 无 |
| `service.py` | 总指挥：按注释里的 1-2-3-4 步骤串流程 | 无（只调用别人） |
| `repository.py` | 把知识库 chunk 解析成结构化数据（课程/职业/规则），带缓存 | 无 |
| `models.py` | 内部数据结构定义（dataclass） | 无 |
| `agents/rule_engine.py` | 硬规则：资格过滤、学分、缺口、兜底排序 | 无 |
| `agents/recommendation_agent.py` | AI 选课写理由 + 代码校验 + 兜底 | 有 |
| `agents/role_mapper.py` | 自由职业→9 个技能标签 | 有 |
| `interface.py` | 给其他模块用的公共入口 | 无 |

program_comparison 的 agents：`match_scorer.py`（匹配度，纯代码）、`comparison_agent.py`（AI 压缩表格）。
career_planning 的 agents：`planning_agent.py`（AI 写规划 + 模板兜底）。

测试：`backend/tests/`，36 个单测全部纯逻辑（不连数据库、不调 AI），`python -m pytest tests/ -q` 运行（pytest 装在本地 venv，未加进 requirements.txt）。

已知限制：画像表暂无已修课程字段；比较的 career 维度暂无数据；`TEST_USER_ID` 单用户占位；竞品学费/截止日期为 2026 申请季快照，以官网为准。
