# Pre-split instructions (historical)

Superseded for ownership and paths by `../AGENTS.md` and `architecture.md`. Retained for the source of existing domain invariants; not current installation guidance.

# AGENTS.md — AI 知识库项目

> Last updated: 2026-10-04
> 本文件是项目的长期记忆，描述当前版本 v0.7.0 的真实结构与运行方式。

## 记忆路由（Memory routing）

- 术语与学习画像词汇：见 `CONTEXT.md`
- 记忆配置（工作根、追踪器、当前任务、产品文档、代码索引）：见 `docs/agents/memory.md`
- 项目愿景与验收标准：`project-vision.md`
- 待办与当前方向：`TODO.md`（用户手工维护，勿随意改动）

冷启动顺序：读本文件 → 读 `CONTEXT.md` → 从 `TODO.md` §"Next" 或用户处解析当前任务 → 若存在则读 `.scratch/<effort>/state.md`。

## 项目定义

**AI Knowledge Base（AI 知识库）** 是一个自动化技术情报收集与分析系统。
当前版本将固定的 Horizon 运行摄入规范化的 SQLite 资产库
（`knowledge/kb.sqlite`），执行确定性的逐条 admission 与可审计的运行记账，
并生成 EN / zh-CN 每日简报。LangGraph/JSON 生产路径已在 ticket 16 退役。

### 核心价值
- 每日自动摄入 AI/LLM/Agent 领域的 Horizon 采集运行（RSS/GitHub 源由 Horizon 配置管理）
- 通过 `kb.ingest.ingest_horizon_run` 完成 **映射 → admission → 记账 → 入库**
- 规范 SQLite 资产库支持 FTS5 检索、导出/备份与下游消费
- 每日简报（EN + zh-CN）通过 SMTP/webhook 投递，未配置时如实报告 `missing_config`

## 项目结构

```text
ai-kb/
├── AGENTS.md                          # 项目记忆文件（本文件）
├── project-vision.md                  # 项目愿景与 go/no-go 验收标准
├── TODO.md                            # 待办事项（可能含用户未完成编辑）
├── pyproject.toml                     # Python 依赖与工具配置
├── .github/workflows/daily-collect.yml # Horizon 生产路径定时任务
├── kb/                                # 规范包
│   ├── model.py                       # 资产/原因码/枚举的单一词表所有者
│   ├── store/                         # SQLite schema、迁移、FTS5、fixtures
│   ├── horizon/                       # Horizon 契约、mapper、源配置治理
│   ├── admission/                     # 个人准入策略（policy/patterns/hollow_words）
│   ├── ingest.py                      # 生产 ingest 路径（映射+admission+记账）
│   ├── digest/                        # 简报选择、渲染、投递
│   └── cli.py                         # `kb` operator CLI
├── scripts/
│   ├── production_run.py              # 生产 ingest + 记账 + 简报入口
│   ├── setup_horizon.py               # 固定 Horizon checkout 安装/更新/doctor
│   └── rehearse_cutover.py            # 切换演练（全部 go/no-go 门禁）
├── horizon-profiles/                  # Horizon 个人相关性画像
├── config/horizon/                    # Horizon 打包模板
├── patterns/                          # Router/Supervisor 演示（保持可导入）
├── tests/                             # pytest 套件（legacy fixture 语料在 tests/fixtures/）
├── knowledge/
│   ├── kb.sqlite                      # 规范 SQLite 资产库
│   ├── export/                        # 导出产物
│   └── digest/                        # 渲染的简报
├── ui/                                # Notion-like 知识库管理面板（Flask，store-backed）
│   ├── app.py                         # Flask API（canonical SQLite 读surface）
│   └── static/                        # SPA（index.html / css / js）
├── mcp_knowledge_server.py            # MCP Server：规范库检索（stdlib only）
├── docs/                              # 产品文档、admission 策略、归档
├── opencode.json
├── .claude/mcp.json
└── .codex/mcp.json
```

## 编码规范

### 数据契约
- 规范资产身份：`horizon:<radar>:<Horizon id>`，在 `kb/horizon/mapper.py` 一次性铸造
- 资产状态、原因码、枚举词表唯一所有者：`kb/model.py`；DDL CHECK 列表由 `kb/store/schema.py` 从它生成
- 简报、UI、MCP 均只读规范库；不再存在 `knowledge/articles/` 直读路径
- legacy→规范映射的迁移 oracle 保留在 `tests/fixtures/legacy_articles/`

### 语言约定
- 代码、JSON 键名、文件名：英文
- 摘要、分析、注释：中文
- 标签：英文小写

## 工作流规则

### 生产路径（Horizon）

```text
Horizon run（固定 checkout）→ ingest → admission + accounting → SQLite store
                                                        ├→ digest
                                                        ├→ MCP
                                                        └→ UI
```

### Agent 协作规则
1. **单一词表**：reason code / 枚举只在 `kb/model.py`；消费方不得重复声明
2. **只读消费**：UI/MCP/digest 通过 `kb.store` reader API 访问，不直接 SQL
3. **空运行**：`status: "empty"` 退出 0；部分失败/失败非零退出
4. **投递诚实**：未配置 SMTP 时报告 `missing_config`，不伪造成功
5. **可追溯**：每个资产保留 Horizon 运行来源与 admission 决策记录

### CLI 命令

所有命令均在项目根目录执行。

```bash
# 校验固定的 Horizon 环境
uv run python scripts/setup_horizon.py install
uv run python scripts/setup_horizon.py doctor

# 生产 ingest + 记账 + 简报（--live 连接真实 Horizon；--deliver 投递）
uv run python scripts/production_run.py --live --deliver

# 切换演练
uv run python scripts/rehearse_cutover.py

# operator CLI（ingest/digest/serve/export/backup/restore）
uv run python -m kb.cli --help

# Non-LLM 测试
uv run pytest -q -m non_llm

# 预览简报
uv run python -m kb.cli digest --stdout

# 启动知识库管理 UI（http://localhost:5050）
# UI 读取 canonical SQLite 资产库（knowledge/kb.sqlite），
# 来源管理视图编辑 Horizon data/config.json（含启用/禁用与近 7 天采集数）
uv run python ui/app.py
```

### 错误处理
- ingest 条目失败逐条记录原因码并计入记账，不中断整批
- 记账门禁失败时非零退出，CI 硬失败
- 缺失 Horizon checkout / store 时显式报错，不静默降级

## 自动化规则
- GitHub Actions 每日执行 `uv run python scripts/production_run.py --live --deliver`
- 定时工作流只提交 `knowledge/kb.sqlite`、`knowledge/export/`、`knowledge/digest/`
- 简报存在性门禁（`if: always()`）：未渲染简报时硬失败
- 生产工作流使用 `uv sync --frozen` 固定依赖

## 技术栈
- **运行时**：Python 3.12+（uv 管理依赖）
- **采集**：Horizon（固定 checkout，源配置在 Horizon `data/config.json`）
- **存储**：SQLite（`kb/store/` 版本化迁移 + FTS5）
- **投递**：SMTP / webhook（标准库 `smtplib`/`email`）
- **测试**：pytest
- **MCP**：`mcp_knowledge_server.py`（Python stdlib only）
- **UI**：Flask + Vanilla JS/CSS，Notion-like 管理面板

## 实施约束
- LangGraph/JSON 生产路径已退役（ticket 16）；不要重建 `workflows/`、`hooks/`、`prompts/` 或 legacy JSON 写入路径
- `patterns/` 是演示代码，不是生产入口，但应保持可导入
- `TODO.md` 可能包含用户手工编辑，除非任务明确要求，不要顺手改动
