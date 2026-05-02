# AI 知识库
> Last updated: 2026-05-02

AI 知识库是一个本地技术情报流水线，面向 AI、LLM、RAG 和 Agent 工具方向。它从 GitHub、Hacker News、arXiv 和 RSS 源采集最新内容，使用 LLM 做分析整理，并输出结构化 JSON 知识条目，方便检索和下游应用消费。

## 功能

- 采集 AI 相关仓库、新闻、论文和 RSS 文章。
- 为原始条目补充摘要、标签、相关性评分和评分明细。
- 将合格条目发布到 `knowledge/articles/`。
- 维护 `knowledge/articles/index.json`，用于轻量检索。
- 提供基于 stdio 的 MCP Server，支持搜索、查询和统计。
- 通过本地 hook 脚本校验 JSON 格式与条目质量。

## 项目结构

```text
ai-kb/
├── pipeline/                 # 采集、分析、整理、保存流水线
├── hooks/                    # JSON 校验与质量评分
├── scripts/                  # 兼容旧路径的 CLI 入口
├── tests/                    # pytest 测试
├── spec/                     # 需求与技术规格
├── knowledge/
│   ├── raw/                  # 原始采集 JSON
│   └── articles/             # 发布后的知识条目与索引
├── mcp_knowledge_server.py   # JSON-RPC stdio MCP 搜索服务
├── opencode.json             # OpenCode MCP 配置
├── .claude/mcp.json          # Claude Code MCP 配置
└── .codex/mcp.json           # Codex MCP 配置
```

## 环境要求

- Python 3.12+
- `uv`
- `.env` 中可选配置：
  - `GITHUB_TOKEN`
  - `DEEPSEEK_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `OPENAI_API_KEY`

## 初始化

```bash
uv sync
cp .env.example .env
```

按需编辑 `.env`。默认 LLM 提供商是 `qwen`。

## 运行流水线

```bash
uv run python pipeline/pipeline.py --sources github,rss --limit 20
```

常用命令：

```bash
uv run python pipeline/pipeline.py --sources github --limit 5 --dry-run
uv run python pipeline/pipeline.py --sources github --limit 10 --step 1 --step 2
uv run python pipeline/pipeline.py --sources rss --limit 5 --provider openai
uv run python pipeline/pipeline.py --sources github --limit 5 --verbose
```

原始采集结果写入 `knowledge/raw/`。发布后的知识条目写入 `knowledge/articles/`。

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

## MCP 工具

`mcp_knowledge_server.py` 提供三个工具：

| 工具 | 功能 |
| --- | --- |
| `search_articles` | 按关键词搜索文章标题和摘要。 |
| `get_article` | 按 ID 返回完整文章。 |
| `knowledge_stats` | 返回文章总数、来源分布和热门标签。 |

仓库已包含 OpenCode、Claude Code 和 Codex 的 MCP 配置文件。修改配置后重启对应客户端即可加载。

## 开发

运行全部测试：

```bash
uv run pytest -q
```

编译 Python 源码：

```bash
uv run python -m compileall pipeline hooks scripts mcp_knowledge_server.py
```

## 数据契约

发布后的文章 JSON 应包含：

- `id`
- `title`
- `source`
- `source_url`
- `url`
- `collected_at`
- `summary`
- `tags`
- `relevance_score`

常见可选字段包括 `analyzed_at`、`score_breakdown`、`status`、`stars`、`forks`、`language`、`description`、`topics` 和 `audience`。
