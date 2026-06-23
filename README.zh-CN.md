# AI 知识库（AI Knowledge Base）

> 最后更新：2026-06-23  
> English: [README.md](README.md)

面向 AI、LLM、RAG 与 Agent 工具的自动化技术情报系统。当前版本 **0.7.0** 在 `workflows/` 下用 LangGraph 编排工作流：采集 GitHub 与 RSS、LLM 逐条分析、质量审核与修订循环，最终将结构化 JSON 知识条目写入 `knowledge/articles/`；随后由独立的简报 CLI 将当日高优先级阅读推送到邮箱。

## 工作流概览

```text
plan → collect → analyze → review
                          ├─ 通过 → organize → END（重建 index.json）
                          ├─ 未通过且未达上限 → revise → review
                          └─ 未通过且达上限 → human_flag → END
```

- **Planner** — 单次运行策略（限额、阈值等）。
- **Collector** — GitHub Search API + RSS（配置见 `workflows/rss_sources.yaml`）。
- **Analyzer / Reviewer / Reviser** — LLM 分析、五维加权审核、按反馈定向修订。Prompt 文本存放于 `prompts/`（由 `workflows/prompts.py` 加载），不再内联在节点中。
- **Organizer** — 按 `source_url` 去重，写入 `knowledge/articles/<slug>-<YYYYMMDD>-<NNN>.json`。
- **HumanFlag** — 审核循环耗尽后整批写入 `knowledge/pending_review/`（仅本地排查，CI 不提交）。

被跳过或过滤的条目会记入 `knowledge/articles/_skipped.jsonl`（每行一条 JSON：`id`、`source`、`reason`）。

## 项目结构

```text
ai-kb/
├── workflows/               # LangGraph 节点、状态、CLI、RSS 配置
│   ├── prompts.py           # Prompt 模板加载器（提供商覆盖 → 通用回退）
│   └── digest.py            # 每日简报生成 + 邮件发送（标准库 SMTP）
├── prompts/                 # 外置 Prompt 模板（*.txt）
├── scripts/
│   └── build_index.py       # 从磁盘全量重建 knowledge/articles/index.json
├── hooks/                   # JSON Schema 校验与质量评分
├── tests/                   # pytest（non_llm / llm_e2e）
├── notebooks/               # LangGraph 演示 notebook
├── knowledge/
│   ├── articles/            # 已发布 JSON + index.json + _skipped.jsonl
│   └── pending_review/      # 审核循环失败的批次
├── ui/                      # Notion 风格本地管理面板（Flask）
├── mcp_knowledge_server.py  # 基于文章的 MCP 检索（stdio JSON-RPC）
├── openspec/                # 变更提案与能力规格
├── .github/workflows/       # daily-collect.yml、llm-e2e.yml
└── AGENTS.md                # 维护者指南（结构、约定、CLI）
```

## 环境准备

```bash
uv sync
cp .env.example .env
```

按需配置：

| 变量 | 用途 |
|------|------|
| `GITHUB_TOKEN` | GitHub Search API（公开仓库） |
| `LLM_PROVIDER` | `qwen`（默认）、`deepseek` 或 `openai` |
| `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | 各提供商 API Key |

## 运行工作流

```bash
uv run python -m workflows.graph --sources github,rss --limit 20
```

常用变体：

```bash
uv run python -m workflows.graph --sources github --limit 5 --dry-run
uv run python -m workflows.graph --sources rss --limit 5 --provider openai
uv run python -m workflows.graph --sources github,rss --limit 10 --verbose
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag
uv run python -m workflows.graph --sources github,rss --limit 20 --json
```

非 `--dry-run` 运行结束后，图会在末尾**全量重建** `knowledge/articles/index.json`（派生产物，organize 阶段不再增量修补索引）。

手动重建索引：

```bash
uv run python scripts/build_index.py
uv run python scripts/build_index.py --dry-run
```

## 浏览与编辑（UI）

```bash
uv pip install -r ui/requirements.txt
uv run python ui/app.py
```

浏览器打开 http://localhost:5050 — 列表、筛选、搜索、编辑与批量操作。详见 [ui/README.md](ui/README.md)。

## MCP 服务

将本地知识库暴露给 Agent（Cursor、Claude Code、Codex、OpenCode）：

```bash
uv run python mcp_knowledge_server.py
```

工具：`search_articles`、`get_article`、`knowledge_stats`。接入示例见 `opencode.json`、`.claude/mcp.json`、`.codex/mcp.json`。

## 定时采集

GitHub Actions（[`.github/workflows/daily-collect.yml`](.github/workflows/daily-collect.yml)）每日 UTC 08:00 执行：

```bash
uv run python -m workflows.graph --sources github,rss --limit 20 --verbose
```

- 仅提交 `knowledge/articles/` 下新文件（不提交 `pending_review/`）。
- 推送前用 hooks 校验**本次暂存**的新文章 JSON。
- 进入 `human_flag` 时在 CI/本地发出 warning；若需非零退出，请加 `--fail-on-human-flag`。

真实 LLM 端到端验证见 [`.github/workflows/llm-e2e.yml`](.github/workflows/llm-e2e.yml)。

## 邮件简报

运行结束后，可将当日 `study-now` / `save-for-context` 条目（读取自 `knowledge/articles/`，按优先级分组、按 `priority_score` 排序）以邮件形式发给自己：

```bash
uv run python -m workflows.digest --stdout            # 预览，不发送
uv run python -m workflows.digest --since 2026-06-23  # 发送指定日期的简报
```

通过环境变量配置 SMTP（未配置时简报会优雅跳过）：

| 变量 | 用途 |
|------|------|
| `EMAIL_ADDRESS` | 发件地址（设置后才会发送） |
| `EMAIL_PASSWORD` | 发件密码 / 应用专用密码 |
| `SMTP_HOST` / `SMTP_PORT` | 默认 `smtp.gmail.com` / `587` |
| `DIGEST_RECIPIENTS` | 逗号分隔的收件人（默认回退为发件人） |

当 `EMAIL_ADDRESS` 配置为仓库 Secret 时，每日 CI 会自动发送简报。

## 校验文章

```bash
uv run python hooks/validate_json.py tests/fixtures/articles/example-published.json
uv run python hooks/check_quality.py tests/fixtures/articles/example-published.json
```

校验磁盘上的文章（勿把 `index.json` 当文章校验）：

```bash
uv run python hooks/validate_json.py knowledge/articles/github-*.json
uv run python hooks/check_quality.py knowledge/articles/github-*.json
```

OpenCode 写入时也可通过 `.opencode/plugins/validate.ts` 自动校验。

## 数据约定

**文件命名：** `knowledge/articles/{source-slug}-{YYYYMMDD}-{NNN}.json`  
**ID：** 与文件名（去掉 `.json`）一致；正则 `^[a-z0-9-]+-\d{8}-\d{3}$`（小写 slug，禁止冒号）。

**必填字段**（由 `hooks/validate_json.py` 强制）：

- `id`、`title`、`source_url`、`url`、`summary`、`tags`、`status`
- `key_insight`、`category`（单一枚举值）、`relevance_score`（0–1）

**未知则可为 null：** `author`、`published_at` — 使用 JSON `null`，不要用源名称或采集时间占位。

**常见可选字段：** `source`、`collected_at`、`score`、`audience`、`published_at`、`author`。

**索引：** `knowledge/articles/index.json` — 由文章全量生成的精简列表（`id`、`title`、`source`、`source_url`、`category`、`relevance_score`）；不作为文章文件参与校验。

示例 fixture：[tests/fixtures/articles/example-published.json](tests/fixtures/articles/example-published.json)。

## 开发

```bash
uv run pytest -q -m non_llm
uv run python -m compileall workflows hooks scripts mcp_knowledge_server.py
```

### 测试

| 标记 | 用途 |
|------|------|
| `non_llm` | 确定性测试（Mock / 不调用真实 LLM） |
| `llm_e2e` | 真实提供商工作流验证（需 API Key） |

```bash
uv run pytest -q -m non_llm
uv run pytest -q -m llm_e2e
```

## 延伸阅读

- [AGENTS.md](AGENTS.md) — 约定、工作流规则、面向 Agent 的 CLI 说明
- [CHANGELOG.md](CHANGELOG.md) — 版本变更记录
- [project-vision.md](project-vision.md) — 项目愿景与 go/no-go 标准
- [docs/archive/](docs/archive/) — 历史审计与策略备忘（2026-05）
