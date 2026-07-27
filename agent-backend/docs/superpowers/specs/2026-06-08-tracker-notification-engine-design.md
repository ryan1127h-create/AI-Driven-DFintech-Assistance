# 设计 — Tracker 通知引擎(#5 主动提醒深化,真发邮件)

> **状态**:已确认(brainstorm 2026-06-08)· 待写实现计划
> **范围**:#5 Tracker(`agents/tracker/{reminders,agent}.py`)+ 新 `common/notifier.py` + `common/{profile,config}.py` + `supervisor.py` + 配套数据/测试/文档
> **前置**:Tracker v2(`docs/08-tracker-v2-design.md`)已落地:状态翻译 + 时间线 + eta + 与 #4 缺件联动 + 里程碑提醒(consent/channels/frequency-off/urgency/already_sent 去重参数)。
> **合规/架构基线不变**:裁决归规则(确定性引擎),叙述/投递归适配器;外部系统可插拔 + 优雅降级;离线可测;凭据不入库。

---

## 1. 背景与问题

PDF 需求 7「Application status tracking and proactive nudges」中,Tracker v2 已覆盖 in-app/email 渠道枚举、缺件/offer/注册里程碑、个性化 next step。**未满足的缺口**:

1. **配置通知偏好**:契约 §1.2 列了 `configure_reminders` intent,但 tracker 只实现了 `get_application_status`——偏好只读回显,无法变更。
2. **daily_digest 未区分**:`frequency` 定义了 `immediate/daily_digest/off`,但 `build_reminders` 只对 `off` 短路,immediate 与 digest 行为相同。
3. **无投递模型**:`already_sent` 参数存在但无人持久化/使用;提醒只是 inline 返回,没有「现在该发什么 + 已发去重」。
4. **不能真发邮件**:PDF「send notifications through approved channels: email」——v2 没有任何真实发送。

本设计聚焦把 Tracker 做成**真正的通知引擎**(招生数据范围内),并**真能发邮件**。

### 1.1 已确认的关键决定

- **状态模型**:sent-state 与偏好变更都**携带在 `UserProfile` 上**(非外部 store)。
- **可配置偏好范围**:channels + frequency + **按里程碑静音**(`muted_milestones`)。
- **裁决/投递分离**:引擎决定「发什么」(确定性、可测);真正发送交给可插拔 `Notifier`。
- **优雅降级**:配了 SMTP 凭据→真发邮件;未配置/测试→record-only 离线。
- **去重语义**:按 reminder `key`;digest 派发时记录其包含的全部子 key → 同一条提醒在任何 frequency 下只发一次。
- **读写分离**:`handle`(读状态)只做 `due_now` 预览,**不写 log、不发信**;只有显式 `dispatch_due` 写 log + 发信。

---

## 2. Schema 增量(`common/profile.py`)

```python
class NotificationPrefs(BaseModel):
    channels: list[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.in_app])
    frequency: NotificationFrequency = NotificationFrequency.immediate
    muted_milestones: list[str] = Field(default_factory=list)   # NEW: 被静音的里程碑 key

class NotificationRecord(BaseModel):                            # NEW
    key: str                 # reminder key, e.g. "offer_acceptance:2026-07-15"
    date: str                # ISO date dispatched
    channels: list[str]      # channels attempted
    delivered: bool = True   # False if a real send failed (record kept for dedup+audit)

class UserProfile(BaseModel):
    ...
    email: str | None = None                                   # NEW: recipient for email channel
    notification_log: list[NotificationRecord] = Field(default_factory=list)  # NEW: carried sent-state
```

`muted_milestones` 的合法值 = 已知里程碑 key(见 §4 `_MILESTONES`)。`email` 缺失时 email 渠道被跳过。

---

## 3. 配置 + Notifier 接缝

### 3.1 `common/config.py`(扩展)
新增(与现有 DeepSeek/embedding 读取同构,优先级 **env > `data/.smtp.json` > 无**):
- `get_smtp_host() / get_smtp_port()(默认 587) / get_smtp_username() / get_smtp_password() / get_smtp_from()(默认 = username) / get_smtp_use_tls()(默认 True)`
- `smtp_configured() -> bool`:host + username + password 齐备即真。
- `data/.smtp.json` 形如 `{"smtp_host":"...","smtp_port":587,"smtp_username":"...","smtp_password":"...","smtp_from":"...","smtp_use_tls":true}`。
- **`.gitignore` 增加 `data/.smtp.json`**;凭据**绝不硬编码**。

### 3.2 `common/notifier.py`(新)
```python
class Notifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...

class RecordingNotifier:           # 离线默认:不联网,直接返回 True(实际记录在 dispatch_due)
    def send(self, to, subject, body) -> bool: return True

class SmtpEmailNotifier:           # 真发:smtplib + EmailMessage + STARTTLS
    # 读 config 的 smtp_* ;失败 -> 返回 False(记录失败,不抛、不断流程)
    def send(self, to, subject, body) -> bool: ...

def get_notifier() -> Notifier:    # 工厂:smtp_configured() -> SmtpEmailNotifier 否则 RecordingNotifier
```
- `SmtpEmailNotifier.send`:构造 `EmailMessage`(from=config from,to,subject,纯文本 body),`smtplib.SMTP(host,port)` → `starttls()`(若 use_tls)→ `login(user,pwd)` → `send_message`;任何异常捕获 → 返回 `False`。
- **这是「换发信方式只改配置/加适配器」的接缝**(同 `Retriever`/`Fetcher`)。

---

## 4. 引擎(`agents/tracker/reminders.py`)

### 4.1 mute 门控
`build_reminders(profile, today)`(现有)在 consent/off/窗口/状态门控基础上,**跳过 `name in profile.notification_prefs.muted_milestones`**。返回的仍是「当前相关提醒」集合(与已发无关,供展示)。

### 4.2 Notification + due_now
```python
@dataclass
class Notification:
    kind: str               # "single" | "digest"
    channels: list[str]
    date: str               # ISO (today)
    subject: str
    message: str
    urgency: str            # info|soon|urgent (digest 取最紧急)
    reminder_keys: list[str]

def due_now(profile, today=None) -> list[Notification]:
    候选 = build_reminders(profile, today)            # 已过 consent/off/mute/窗口/状态门控
    sent = {rec.key for rec in profile.notification_log}
    pending = [r for r in 候选 if r.key not in sent]   # 去重(频控)
    if not pending: return []
    channels = [c.value for c in prefs.channels]
    if frequency == immediate:
        return [Notification("single", channels, today, subject(r), r.message, r.urgency, [r.key]) for r in pending]
    if frequency == daily_digest:
        return [Notification("digest", channels, today, digest_subject, digest_body(pending),
                             max_urgency(pending), [r.key for r in pending])]
    # off 已在 build_reminders 返回 []
```
- `subject(r)`:如「NUS MSc DFinTech 提醒:确认接受录取」;`digest_subject`:如「NUS MSc DFinTech:你有 N 条待办提醒」;`digest_body`:逐条 message 汇总。

### 4.3 dispatch_due(副作用:发信 + 写 log)
```python
def dispatch_due(profile, today=None, notifier=None) -> list[Notification]:
    notifier = notifier or get_notifier()
    notes = due_now(profile, today)
    for n in notes:
        delivered = True
        if "email" in n.channels:
            if profile.email:
                ok = notifier.send(profile.email, n.subject, n.message)
                delivered = delivered and ok
            else:
                pass  # 无邮箱 -> email 渠道跳过(in_app 仍算已投递)
        # in_app: record-only(无外部投递)
        for k in n.reminder_keys:                       # digest 记录全部子 key -> 跨 frequency 只发一次
            profile.notification_log.append(NotificationRecord(key=k, date=today, channels=n.channels, delivered=delivered))
    return notes
```
- 默认 `get_notifier()`;测试注入 `RecordingNotifier` 或 monkeypatched SMTP。
- 真发邮件**仅当** `email` 在 channels、`profile.email` 存在、且 notifier 可用(配了 SMTP)。其余 record-only。
- 发送失败 → `delivered=False` 仍写 log(去重 + 审计),不抛、不断流程。

---

## 5. `configure_reminders` intent(`agents/tracker/agent.py` 新 `configure`)

```python
def configure(profile, slots) -> AgentResponse:
    # slots 例:{"channels":["in_app","email"], "frequency":"daily_digest",
    #            "mute":["application_deadline"], "unmute":["offer_acceptance"]}
```
- **校验**:channels ⊆ NotificationChannel;frequency ∈ NotificationFrequency;mute/unmute 的 key ∈ 已知里程碑。任一非法 → `AgentResponse.needs([...], "...")`(`need_clarification`,列出非法字段,不静默吞)。
- **应用**:构造新 `NotificationPrefs`(channels/frequency 覆盖;`muted_milestones` = 旧 ∪ mute − unmute),赋回 `profile.notification_prefs`。
- **返回**:`status="ok"`,确认 speakable(如「已更新:邮件+应用内通知,每日汇总;已静音『提交申请材料』提醒。」),`data.notification_prefs`(新值)。
- **supervisor 路由**:`supervisor.route` 把 `configure_reminders` → `tracker.configure`(现仅路由 `get_application_status` → `tracker.handle`)。

---

## 6. `handle`(get_application_status)增量
`data` 增加:
- `due_now`: `[Notification 序列化]`(**预览,只读;不写 log、不发信**)。
- `notification_prefs` 扩展出 `muted_milestones`(及现有 channels/frequency)。
现有 `reminders`(相关集)、`timeline`、`deadlines`、`escalation_packet` 等保留不变。

---

## 7. 数据 / 演示
- `common/mock_data.py`:给某 demo profile 配 `email`、多条临近 deadline、空 `notification_log`,以演示 digest 合并与去重(dispatch 两次:第二次 `due_now` 为空)。
- `run.py`(可选):加 `notify` 演示:打印 `due_now` → `dispatch_due`(record-only,因无 SMTP)→ 再 `due_now` 为空。

---

## 8. 测试(`tests/test_tracker.py` + 新 `tests/test_notifier.py`)
**始终离线**:
- `configure`:改 channels/frequency/mute/unmute 生效;非法值 → `need_clarification`;mute 后 `build_reminders` 抑制该里程碑。
- digest:多条 due → 1 条 digest Notification(含全部子 key);immediate → 每条一个 single。
- `due_now` 去重:`dispatch_due` 后 `due_now` 为空;digest 派发后切 immediate 不重发(子 key 已记录)。
- `off` → `due_now` 为空;`handle` 的 `due_now` 预览**不**改 `notification_log`。
- 投递:email 渠道但 `profile.email` 缺失 → 跳过该渠道(in_app 仍记录);用 `RecordingNotifier` 验证 record-only。
- `SmtpEmailNotifier`:**monkeypatch `smtplib.SMTP`**,断言 starttls/login/send_message 被调且邮件字段(to/from/subject/body)正确;**不碰真实网络**。SMTP `send` 抛异常 → 返回 False、`delivered=False`、不抛。
- 真实发送集成测试:`smtp_configured()` 为假时 `pytest.skip`(沿用 live-embedding 套路)。
- **安全**:断言代码中无硬编码凭据(凭据只经 config 读取)。

---

## 9. 文件清单(预期触点)
| 文件 | 改动 |
|------|------|
| `common/profile.py` | `muted_milestones`、`email`、`NotificationRecord`、`notification_log` |
| `common/config.py` | `get_smtp_*` + `smtp_configured()` |
| `common/notifier.py` | 新:`Notifier`/`RecordingNotifier`/`SmtpEmailNotifier`/`get_notifier` |
| `.gitignore` | 加 `data/.smtp.json` |
| `agents/tracker/reminders.py` | mute 门控、`Notification`、`due_now`、`dispatch_due` |
| `agents/tracker/agent.py` | `handle` 加 `due_now` 预览;新 `configure` |
| `supervisor.py` | 路由 `configure_reminders` → `tracker.configure` |
| `common/mock_data.py` | demo profile:email + 多 deadline + 空 log |
| `run.py` | 可选 notify 演示 |
| `docs/08-tracker-v2-design.md` · `docs/02-interface-contracts.md §4#5` | 更新 |
| `CHANGELOG.md` · `docs/00-project-overview.md` | 记录 |
| `tests/test_tracker.py` · `tests/test_notifier.py` | 上述 + 回归 |

---

## 10. 非目标(YAGNI)
- 不做 quiet hours / 时间粒度(系统按日期工作)。
- 不做 HTML 邮件模板 / 退订链接(纯文本)。
- 不绑定第三方发信 API(只通用 SMTP)。
- 不扩生命周期里程碑(module selection / graduation)——另一个方向。
- 不做真实推送调度器(dispatch 由系统/demo 显式触发)。
