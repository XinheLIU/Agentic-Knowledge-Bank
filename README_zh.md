# AI 知识库
> Last updated: 2026-05-06

AI 知识库是一个本地技术情报系统，面向 AI、LLM、RAG 和 Agent 工具方向。`0.5.0` 版本已从旧的线性 `pipeline/` 迁移到 `workflows/` 下的 LangGraph 工作流。

## v0.5.0 变化

- `workflows/` 成为唯一支持的运行时入口。
- 工作流显式建模为 `Planner -> Collector -> Analyzer -> Reviewer -> Reviser -> Organizer`，异常终点为 `HumanFlag`。
- `pipeline/` 和 `scripts/` 已移除，不保留向后兼容。
- 数据采集仍支持 GitHub 与 RSS。

迁移原因与权衡见 [spec/upgrade-0.4.0-to-0.5.0.md](/Users/xhl/Desktop/Personal-Projects/Learning/AI和多Agent行动营/ai-kb/spec/upgrade-0.4.0-to-0.5.0.md:1)。

## 项目结构

```text
ai-kb/
├── workflows/               # LangGraph 节点、状态、图 CLI、RSS 配置
├── patterns/                # Router / Supervisor 模式示例
├── hooks/                   # JSON 校验与质量评分
├── tests/                   # pytest 测试
├── notebooks/               # 工作流演示 notebook
├── spec/                    # 需求、技术规格、升级说明
├── knowledge/
│   ├── raw/                 # 原始采集 JSON
│   ├── articles/            # 发布后的知识条目与索引
│   └── pending_review/      # 审核循环失败后的待人工处理数据
├── mcp_knowledge_server.py  # JSON-RPC stdio MCP 搜索服务
├── opencode.json            # OpenCode MCP 配置
├── .claude/mcp.json         # Claude Code MCP 配置
└── .codex/mcp.json          # Codex MCP 配置
```

## 初始化

```bash
uv sync
cp .env.example .env
```

`.env` 中按需配置：

- `GITHUB_TOKEN`
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- `OPENAI_API_KEY`

默认 LLM 提供商是 `qwen`。

## 运行工作流

```bash
uv run python -m workflows.graph --sources github,rss --limit 20
```

常用命令：

```bash
uv run python -m workflows.graph --sources github --limit 5 --dry-run
uv run python -m workflows.graph --sources rss --limit 5 --provider openai
uv run python -m workflows.graph --sources github,rss --limit 10 --verbose
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag
```

审核通过的条目写入 `knowledge/articles/`。超过审核迭代上限的批次写入 `knowledge/pending_review/`。

## 定时运行

每日 GitHub Actions 使用的入口为：

```bash
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag
```

这意味着自动化环境把 `HumanFlag` 视为失败信号。`knowledge/pending_review/` 仅用于本地排查，不会被定时工作流提交到仓库。

## 校验文章

```bash
uv run python hooks/validate_json.py tests/fixtures/articles/example-published.json
uv run python hooks/check_quality.py tests/fixtures/articles/example-published.json
```

校验生成的文章：

```bash
uv run python hooks/validate_json.py knowledge/articles/*.json
uv run python hooks/check_quality.py knowledge/articles/*.json
```

## 开发

```bash
uv run pytest -q -m non_llm
uv run python -m compileall workflows hooks mcp_knowledge_server.py
```

## 测试

当前测试明确分成两条独立路径：

```bash
uv run pytest -q -m non_llm
uv run pytest -q -m llm_e2e
```

`non_llm` 是默认的确定性测试路径。`llm_e2e` 是独立的真实 LLM 端到端验证，需要配置 provider 凭证。详情见 [spec/testing-strategy.md](/Users/xhl/Desktop/Personal-Projects/Learning/AI和多Agent行动营/ai-kb/spec/testing-strategy.md:1)。

## 数据契约

发布后的文章 JSON 至少需要满足 hook 约束：

- `id`
- `title`
- `source_url`
- `summary`
- `tags`
- `status`

工作流通常还会输出 `source`、`url`、`collected_at`、`score`、`audience`、`relevance_score`、`category`、`key_insight`。
