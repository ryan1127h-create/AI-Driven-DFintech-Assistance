# Technical Design — 分级刷新管线(`refresh/`)

> **状态**:设计草案 · 已与用户确认
> **目标**:让"对外展示的真实数据"(先做 #7 课程目录)可由抓取 + 模型整理自动更新,但**用分级 + 例外审核**控制风险,使人工随"风险/变化"增长而非"专业数量"增长。
> **铁律**:运行时引擎只读确定 JSON;刷新是录入时动作,复用现有审核/版本/审计设施。

---

## 1. 为什么不实时爬、为什么要分级

实时爬 + LLM 总结直接对外 = 把不确定性放进运行时(幻觉、合规、不可测)。所以:抓取与服务分离;大部分数据走**自动放行**,人只看**例外**。详见 docs/03、需求文档关于 "curated and approved / verified vs synthesis"。

## 2. 先接的数据:`module_catalog`

NUS 第一手课程目录(权威源,低风险):
```jsonc
{
  "source_url": "https://...nus.../catalog",
  "fetched_at": "2026-05-01",
  "modules": [
    {"code": "DFT5101", "name": "...", "credits": 4, "description": "...", "source_url": "..."}
  ]
}
```
每条带 provenance(来源 + 日期),前端可标"截至 X 日,来源 X"。

## 3. 模块(全部在 `refresh/`,不碰 agents)

```
refresh/
├─ sources.py    # RefreshSource 注册表: 路径/schema/可信度/默认fetcher/异常检测函数
├─ fetcher.py    # Fetcher 协议 + SampleFetcher(读本地样例; 真实爬虫=未来插件)
├─ summarize.py  # 原始内容→结构化草案(dict 直通; 文本→DeepSeek)
├─ anomaly.py    # 异常检测(课程消失/同code改名/学分突变)
├─ tiering.py    # 决策: auto_publish | needs_review | rejected
├─ pending.py    # 待审队列 data/_pending/ + 列出/批准
├─ pipeline.py   # 编排: 抓取→整理→校验→异常→决策→发布/入审
└─ run.py        # CLI
```

## 4. 平衡放行策略(`tiering.decide`)

```
schema 不过            → rejected(永不发布)
首次接入(无基线)      → needs_review(建立基线, 仅一次)
来源不可信             → needs_review
有异常                 → needs_review
以上都无 + 可信源       → auto_publish(仅记审计)
```
**扩到新专业**:首次审一次,之后日常刷新仅在"有异常/有变化"时报人。

## 5. 异常检测(`anomaly.detect_catalog_anomalies`)

- `module_removed`:已有 code 在新数据中消失(可能抓取失败/页面改版)
- `name_changed`:同 code 名称变化
- `credits_changed`:同 code 学分变化
- 新增课程视为正常(不报异常,仅计数)
- 字段缺失/类型错 → 由 schema 校验拦截

## 6. 编排(`pipeline.run`)

```
fetch → summarize(→draft) → validate(schema) → 计算 is_first/current
      → anomaly(current, draft) → decide(...)
   ├─ rejected      → 返回错误, 不写
   ├─ auto_publish  → 无diff则no_change; 否则 归档+写入+审计(action=refresh)
   └─ needs_review  → 写 data/_pending/(草案+diff+异常+原因+来源), 审计
```

## 7. 待审与批准(`pending`)

- `queue()`:写 `data/_pending/<source>.<ts>.json`(含 draft/diff/anomalies/reasons/provenance/status=pending)
- `list_pending()` / `approve(file, admin)`:批准 = 归档+写入目标+审计(action=refresh, approved=true),并标记 pending 已处理

## 8. 复用与隔离

- 复用 `admin.audit`(归档/diff/审计)、`admin.schemas`(校验,新增 `ModuleCatalog`)
- 真实爬虫 = 实现 Fetcher 接口的插件,**不改管线**(SampleFetcher 先顶替,离线可测)

## 9. 验证

- `anomaly` / `tiering` / `pipeline`(首次→人工、无变化→no_change、小变→自动、消失→人工)/ `pending`(队列+批准)全用临时文件 + SampleFetcher,**离线可测,不依赖网络/LLM**。

## 10. 实施顺序
ModuleCatalog schema → 基线数据 → fetcher → anomaly → tiering → pipeline → pending → CLI → 测试
