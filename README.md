# AI Knowledge Base
> Last updated: 2026-05-02

AI Knowledge Base is a local technical intelligence pipeline for AI, LLM, RAG, and agent tooling. It collects current items from GitHub, Hacker News, arXiv, and RSS sources, analyzes them with an LLM, and writes structured JSON knowledge entries for search and downstream use.

## What It Does

- Collects AI-related repositories, stories, papers, and RSS articles.
- Enriches raw items with summaries, tags, relevance scores, and score breakdowns.
- Publishes qualified entries to `knowledge/articles/`.
- Maintains `knowledge/articles/index.json` for lightweight discovery.
- Provides a stdio MCP server for article search, lookup, and stats.
- Validates article JSON and quality through local hook scripts.

## Project Layout

```text
ai-kb/
├── pipeline/                 # Collection, analysis, organization, and save flow
├── hooks/                    # JSON validation and article quality checks
├── scripts/                  # Backward-compatible CLI entry points
├── tests/                    # pytest suite
├── spec/                     # Requirements and technical specs
├── knowledge/
│   ├── raw/                  # Collected raw JSON
│   └── articles/             # Published JSON knowledge entries and index
├── mcp_knowledge_server.py   # MCP search server over JSON-RPC stdio
├── opencode.json             # OpenCode MCP config
├── .claude/mcp.json          # Claude Code MCP config
└── .codex/mcp.json           # Codex MCP config
```

## Requirements

- Python 3.12+
- `uv`
- Optional API keys in `.env`:
  - `GITHUB_TOKEN`
  - `DEEPSEEK_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `OPENAI_API_KEY`

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` with the providers you plan to use. The default LLM provider is `qwen`.

## Run The Pipeline

```bash
uv run python pipeline/pipeline.py --sources github,rss --limit 20
```

Useful variants:

```bash
uv run python pipeline/pipeline.py --sources github --limit 5 --dry-run
uv run python pipeline/pipeline.py --sources github --limit 10 --step 1 --step 2
uv run python pipeline/pipeline.py --sources rss --limit 5 --provider openai
uv run python pipeline/pipeline.py --sources github --limit 5 --verbose
```

Raw collection output is written to `knowledge/raw/`. Published knowledge entries are written to `knowledge/articles/`.

## Validate Articles

```bash
uv run python hooks/validate_json.py tests/fixtures/articles/example-published.json
uv run python hooks/check_quality.py tests/fixtures/articles/example-published.json
```

For generated articles:

```bash
uv run python hooks/validate_json.py knowledge/articles/*.json
uv run python hooks/check_quality.py knowledge/articles/*.json
```

## MCP Tools

`mcp_knowledge_server.py` exposes three tools:

| Tool | Purpose |
| --- | --- |
| `search_articles` | Search article titles and summaries by keyword. |
| `get_article` | Return a full article by ID. |
| `knowledge_stats` | Return total count, source distribution, and top tags. |

The repo includes MCP config files for OpenCode, Claude Code, and Codex. Restart the client after editing the config.

## Development

Run the full test suite:

```bash
uv run pytest -q
```

Compile Python sources:

```bash
uv run python -m compileall pipeline hooks scripts mcp_knowledge_server.py
```

## Data Contract

Published article JSON files should include:

- `id`
- `title`
- `source`
- `source_url`
- `url`
- `collected_at`
- `summary`
- `tags`
- `relevance_score`

Common optional fields include `analyzed_at`, `score_breakdown`, `status`, `stars`, `forks`, `language`, `description`, `topics`, and `audience`.
