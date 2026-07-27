# Technical Design — Navigator v2 (#7 深化:学习路径规划)

> **v3 起(2026-06-08)进度感知 + LLM 受约束选课**:推荐改为「规则候选池(岗位课 ∪ 按缺口纳入,排除已修)→ LLM 在候选内挑选/排序 + 校验 → 确定性兜底」;新增 `module_skills.json`(已修→技能、缺口→候选,一份两用);区分 `recommend_courses`/`recommend_career_path`;已修代码软校验。见 [v3 spec](superpowers/specs/2026-06-08-navigator-progress-aware-design.md) 与 [plan](superpowers/plans/2026-06-08-navigator-progress-aware.md)。
> **状态**:草案 · 已确认 · 接上需求文档 #8(课程规划与毕业管理)
> 四项整合:① 先修关系感知 ② 学分与毕业进度 ③ 学期排布/学习路径 ④ what-if(全日制 vs 兼读)。规划在纯 Python,用已富化的本地 catalog,运行时不联网。

## 1. 数据富化(module_catalog)
- `CatalogModule` 新增可选:`semesters: list[int]`(开课学期)、`prereq_tree`(NUSMods 先修树:`{"and"/"or":[...]}` 或课程码字符串)、`workload_hours: float|None`(workload 数组求和)。
- `NusmodsFetcher.map` 一并捕获(semesterData.semester / prereqTree / sum(workload))。
- 重抓真实数据经 refresh 管线(`trusted=true`,仅增字段、无异常 → 自动发布)。

## 2. Profile
- 新增 `completed_modules: list[str]`(已修课程码)——用于先修判定与毕业进度。
- 路径复用现有 `application_type`(full_time / part_time)。

## 3. 先修判定(`planner.prereq_status`)
- 递归求值 prereqTree:字符串=需已修该课;`{"and":[...]}` 全满足;`{"or":[...]}` 任一满足;`None`=无先修。
- 对照 `completed_modules` → `satisfied: bool` + `missing: list[str]`。

## 4. 学分与毕业进度(`planner.graduation_progress`)
- 毕业学分要求可配置(默认 `GRAD_CREDITS = 40`,MSc DFT 课程学分,标注 synthetic)。
- 输出:`required`、`completed_credits`、`planned_credits`(推荐模块学分和)、`remaining`(= max(0, required − completed − planned))。

## 5. 学期排布(`planner.build_study_plan`)
- 每学期载量上限:full_time = 20 MC,part_time = 8 MC(可配置)。
- 按模块 `semesters` 约束铺排(只 Sem k 开的进 Sem k 的槽);无学期信息=可放任意学期。
- 每学期累计学分/工时;超过上限 → `overload: true`。
- 输出:`pathway`、`semesters: [{term, modules, credits, workload_hours, overload}]`。

## 6. what-if
- 对 `full_time` 与 `part_time` 各算一遍 `build_study_plan`,输出两路径对比(学期数、每学期载量)。

## 7. Agent / 渲染
- `#7` 在原推荐基础上增加:`prereq_warnings`(未满足先修的模块)、`graduation_progress`、`study_plans`(两路径)。
- 学生页:毕业进度 + 学期路径表 + 先修提醒。

## 8. 验证
prereqTree 递归(string/and/or/缺先修)、学分进度、学期铺排(开课约束+超载)、两路径 what-if、schema 富化向后兼容;全离线确定性(用本地富化 catalog)。
