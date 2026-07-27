# Technical Design — Tracker v2 (#5 深化)

> **v3 起(2026-06-08)通知引擎**:新增 `configure_reminders`(改 channels/frequency/按里程碑静音)、`daily_digest` 分组、`due_now`/`dispatch_due` 去重投递模型,并经可插拔 `Notifier`(`common/notifier.py`)**真发邮件**(SMTP via `common/config.py`,未配置则离线 record-only)。sent-state 携带在 `UserProfile.notification_log`。见 [v3 spec](superpowers/specs/2026-06-08-tracker-notification-engine-design.md) 与 [plan](superpowers/plans/2026-06-08-tracker-notification-engine.md)。
> **状态**:设计草案 · 已确认 · 配套 [schema](01-user-profile-schema.md) / [contracts](02-interface-contracts.md)
> 四项整合:① 状态历史时间线 + 预计日期 ② 与 #4 清单打通 ③ 通知偏好 ④ 主动里程碑提醒。运行时仍 mock 招生系统;裁决在纯 Python。

## 1. Profile 新增
- `Application.status_history: list[StatusEvent]`,`StatusEvent = {status_code, date(ISO), note?}`(最近一条应与 `status_code` 一致)。
- `UserProfile.notification_prefs: NotificationPrefs`:
  - `channels: list[NotificationChannel]`(`in_app | email`,默认 `[in_app]`)
  - `frequency: NotificationFrequency`(`immediate | daily_digest | off`,默认 `immediate`)

## 2. 状态翻译 + 预计日期(`status_translations.json` + statemachine)
- 每个状态加可选 `eta_days`(到下一步预计天数)。`StatusTranslations` schema 的 entry 增加可选 `eta_days`(admin 录入工具同步)。
- `statemachine.estimated_next_date(status, since: date) -> str|None` = `since + eta_days`。
- `statemachine.build_timeline(history) -> [{status_code, human_status, date, note}]`(按日期升序,翻译人话)。

## 3. 与 #4 清单打通
- 状态 `DOCS_REQUIRED` 时,agent 调 `agents.checklist.engine.build_checklist`,取 `status in (missing, rejected)` 的项 → `outstanding_documents: [{key,label,status}]`,并把 `next_step` 具体化("还缺:成绩单(被退)…")。

## 4. 通知偏好 + 里程碑提醒(`reminders.py`)
- **偏好**:`frequency == off` → 不产生提醒;每条 `Reminder` 带 `channels = prefs.channels`。
- **里程碑状态门控**:`_MILESTONE_STATUS` 把 deadline_key 映射到所需状态;当前状态不符则跳过:
  - `offer_acceptance → OFFER`,`document_deadline → DOCS_REQUIRED`,`registration → ACCEPTED`,`application_deadline → None`(申请期常驻)
- 保留:consent(`reminders` 开关)、频控(`already_sent`)、紧急度(≤3 urgent / ≤7 soon)。

## 5. Agent v2 输出(`agent.py`)
`data` 增加:`timeline`、`estimated_next_date`、`outstanding_documents`(DOCS_REQUIRED 时)、`reminders`(带 channels)、`notification_prefs`。`speakable` 汇总当前状态 + 预计日期 + 最紧急提醒。

## 6. 渲染与数据
- `mock_data`:给 profile 4 加 `status_history` + `notification_prefs`(复用其 DOCS_REQUIRED + 被退 transcript 演示 #4↔#5)。
- `student` 暂不强制改(#5 不在学生三块内);`run.py status` 显示时间线 / 缺件 / 偏好。

## 7. 验证
扩展 `tests/test_tracker.py`:时间线翻译、eta 预计日期、DOCS_REQUIRED 联动缺件、prefs `off`/channel、里程碑状态门控(OFFER 才提醒接受录取);全离线确定性;原有用例同步。
