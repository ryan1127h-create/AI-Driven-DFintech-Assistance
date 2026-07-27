# 团队协作上手指南

> 给队友的"如何加入并一起开发"说明。配合 [接口契约](02-interface-contracts.md) 与 [user profile schema](01-user-profile-schema.md) 使用。

## 0. 一次性:把项目放上 GitHub(由你/owner 做)

本地已初始化 git。创建共享远程并推送:
1. 在 GitHub 新建一个**空**仓库(不要勾 README/.gitignore,避免冲突),例如 `msc-dft-assistant`。
2. 在项目目录执行:
   ```bash
   git remote add origin https://github.com/<你的账号>/msc-dft-assistant.git
   git branch -M main
   git push -u origin main
   ```
3. 在 GitHub 仓库 **Settings → Collaborators** 邀请队友(或建一个 Organization/Team)。

> ⚠️ **绝不提交 API key**:`.gitignore` 已忽略 `data/.deepseek.json`。每个人用各自的 key,在网页 `/settings` 或环境变量里配,**不要写进代码或提交**。

## 1. 队友首次上手(每个队友做一次)

```bash
git clone https://github.com/<你的账号>/msc-dft-assistant.git
cd msc-dft-assistant
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
python -m pytest tests/ -q                          # 应全绿(离线)
python run.py --list-profiles                       # 跑个 demo
```
配自己的 DeepSeek key:启动 `python -m student.webapp` → 浏览器 `/settings` 填。

## 2. 谁负责什么(分工)

本仓库当前实现的是 MVP 第 4–7 项(`agents/` + `admin/` + `student/` + `refresh/`)。团队其余模块按接口契约对接:

| 模块 | 目录 | 负责人 | 对接点 |
|------|------|--------|--------|
| 对话 / 意图识别 | (待建) | 队友 A | 调用 `supervisor.route(intent, profile)`,intent 见契约 §1.2 |
| RAG / 知识检索 | (待建) | 队友 B | #4/#6 解释/叙述时的知识来源(契约 §3) |
| Escalation 工单 | (待建) | 队友 C | 消费 `AgentResponse.escalation`(契约 §2) |
| #4–#7 + 数据刷新 | `agents/ admin/ student/ refresh/` | 你 | 已实现 |

> 新模块也放进这个仓库各自的目录;**通过契约里的函数/数据结构对接,不要直接改别人的内部实现**。

## 3. 协作流程(分支 + PR)

不要直接推 `main`。每人开分支:
```bash
git checkout -b feature/<你的模块>-<简述>      # 如 feature/rag-retriever
# ... 改代码 ...
python -m pytest tests/ -q                      # 先本地跑过测试
git add -A && git commit -m "feat: ..."
git push -u origin feature/...
```
然后在 GitHub 开 **Pull Request**,至少一人 review 后合并到 `main`。

**约定**:
- 改了公共接口(`common/`、`supervisor.py`、契约文档)→ 群里同步 + 相关人 review。
- 每个 PR 必须 `pytest` 全绿。
- 提交信息用前缀:`feat:` / `fix:` / `docs:` / `test:` / `refactor:`。

## 4. 扩展点速查(给队友改时参考)

- 加可编辑数据类型:`admin/schemas.py` 加模型 + `admin/registry.py` 注册。
- 加刷新数据源:`refresh/sources.py` 注册 + `refresh/anomaly.py` 异常函数 + schema。
- 加 agent:实现 `handle(profile, slots) -> AgentResponse`,在 `supervisor.py` 注册 intent。

## 5. 不要提交的东西(已在 .gitignore)
`data/.deepseek.json`(密钥)、`data/_versions/`、`data/_audit_log.jsonl`、`data/_pending/`、`__pycache__/`、`.venv/`。
