# Technical Design — 管理员自然语言录入工具(`admin/`)

> **状态**:设计草案 · 已与用户确认
> **目标**:让管理员用自然语言维护 `status_translations` / `admissions_rules` / `programs_dataset` 等数据,而非手写 JSON。
> **铁律**:**运行时引擎完全不变**。JSON 仍是引擎唯一真相源;LLM 只在"录入时"用一次,把人话编译成 JSON,且必须人工审核后才生效。

---

## 1. 为什么这样设计

把自然语言放到**运行时裁决**会重新引入不确定性和幻觉(资格判断高风险)。因此严格区分:

- **录入时(authoring)**:LLM 把"当前 JSON + 自然语言修改指令" → 完整的新 JSON 草案。
- **审核闸门**:pydantic 校验 + 管理员确认 diff。
- **运行时(runtime)**:引擎读确定的 JSON,**不调 LLM**,27 个确定性测试照常有效。

对应需求文档:"staff can update content without engineering effort" + "curated and approved" + "version-controlled" + "auditability"。

---

## 2. 模块(全部在 `admin/`,不碰 `agents/`)

```
admin/
├─ schemas.py    # 各可编辑数据的 pydantic 模型(本期: StatusTranslations)
├─ registry.py   # target 名 → EditableTarget{路径, schema, 抽取提示, 风险等级}
├─ extract.py    # 当前JSON + 自然语言 → JSON草案(唯一调 DeepSeek 处;无 key 报错)
├─ audit.py      # 版本归档 + diff + append-only 审计日志
└─ author.py     # CLI 编排 + 核心 apply_draft()(可单测)
```

## 3. 流程

```
python -m admin.author status_translations --admin alice
  └─ 输入自然语言修改指令
       │
   extract()  ── DeepSeek ──▶ 完整 JSON 草案   (① 唯一需 key)
       │
   schemas 校验  ──不合法──▶ 打回, 不写入       (② 安全闸门)
       │ 合法
   compute_diff(旧, 新) ──▶ 展示改了哪些字段
       │
   管理员确认 y/n                                (③ 人工审核)
       │ y
   archive_version(旧 → data/_versions/) → 写新文件 → append_audit()
```

## 4. 数据结构

**审计日志**(`data/_audit_log.jsonl`,每行一条 JSON):
```json
{"timestamp":"2026-05-31T10:00:00","target":"status_translations","admin":"alice",
 "instruction":"把 UNDER_REVIEW 的下一步改成'预计3周内出结果'",
 "changed_fields":["translations.UNDER_REVIEW.next_step"],
 "version_archived":"data/_versions/status_translations.20260531_100000.json","approved":true}
```

**版本归档**:写入前把旧文件复制到 `data/_versions/<stem>.<timestamp>.json`,可回滚。

## 5. 风险分级

| target | 风险 | 审核 |
|--------|------|------|
| status_translations | 低 | 确认 diff 即可 |
| programs_dataset | 中 | 必须人工审核(合规) |
| admissions_rules | 高 | 必须招生办批准 |

人工审核闸门(流程第 ③ 步)对所有 target 内建;高风险类型未来可加"双人批准"。

## 6. 扩展新数据类型

只需在 `schemas.py` 加一个 pydantic 模型 + 在 `registry.py` 注册一项(路径/schema/提示词/风险),`extract`/`audit`/`author` 无需改动。

## 7. 验证策略

- `schemas` / `audit` / `diff` / `apply_draft`:单元测试,样例 JSON,**不依赖 LLM**(测试用 tmp 路径,不碰真实 data/)。
- `extract`:需 DeepSeek key,用户实测。
- 运行时引擎:不变,原 27 个测试继续通过。

## 8. 实施顺序

schemas → audit → extract → registry → author → 测试 → (有 key)extract 实测
