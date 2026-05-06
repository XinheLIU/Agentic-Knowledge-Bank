# AI Knowledge Base
> Last updated: 2026-05-06

AI Knowledge Base is a local technical intelligence system for AI, LLM, RAG, and agent tooling. Version `0.5.0` replaces the old linear `pipeline/` flow with a LangGraph workflow under `workflows/`.

## What Changed In v0.5.0

- `workflows/` is now the only supported runtime.
- The workflow is explicit: `Planner -> Collector -> Analyzer -> Reviewer -> Reviser -> Organizer`, with `HumanFlag` as the abnormal terminal path.
- `pipeline/` and `scripts/` were removed. There is no backward compatibility layer.
- GitHub and RSS remain supported collection sources.

See [spec/upgrade-0.4.0-to-0.5.0.md](/Users/xhl/Desktop/Personal-Projects/Learning/AI和多Agent行动营/ai-kb/spec/upgrade-0.4.0-to-0.5.0.md:1) for the migration rationale and tradeoffs.

## Project Layout

```text
ai-kb/
├── workflows/               # LangGraph nodes, state, graph CLI, RSS config
├── patterns/                # Router / Supervisor pattern demos
├── hooks/                   # JSON validation and article quality checks
├── tests/                   # pytest suite
├── notebooks/               # Demo notebooks for the workflow
├── spec/                    # Requirements, tech spec, migration notes
├── knowledge/
│   ├── raw/                 # Collected raw JSON
│   ├── articles/            # Published article JSON and index
│   └── pending_review/      # Failed review-loop batches
├── mcp_knowledge_server.py  # MCP search server over JSON-RPC stdio
├── opencode.json            # OpenCode MCP config
├── .claude/mcp.json         # Claude Code MCP config
└── .codex/mcp.json          # Codex MCP config
```

## Setup

```bash
uv sync
cp .env.example .env
```

Optional API keys:

- `GITHUB_TOKEN`
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- `OPENAI_API_KEY`

Default provider is `qwen`.

## Run The Workflow

```bash
uv run python -m workflows.graph --sources github,rss --limit 20
```

Useful variants:

```bash
uv run python -m workflows.graph --sources github --limit 5 --dry-run
uv run python -m workflows.graph --sources rss --limit 5 --provider openai
uv run python -m workflows.graph --sources github,rss --limit 10 --verbose
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag
```

The Organizer writes approved articles to `knowledge/articles/`. Review-loop failures are written to `knowledge/pending_review/`.

## Scheduled Runs

The daily GitHub Actions workflow uses:

```bash
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag
```

That means `HumanFlag` is treated as a failed run in automation. `knowledge/pending_review/` is an operational fallback for local inspection and is not committed by the scheduled workflow.

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

## Development

```bash
uv run pytest -q -m non_llm
uv run python -m compileall workflows hooks mcp_knowledge_server.py
```

## Testing

Two separate runs are supported:

```bash
uv run pytest -q -m non_llm
uv run pytest -q -m llm_e2e
```

`non_llm` is the default deterministic lane. `llm_e2e` is a separate real-provider workflow verification run and requires provider credentials. See [spec/testing-strategy.md](/Users/xhl/Desktop/Personal-Projects/Learning/AI和多Agent行动营/ai-kb/spec/testing-strategy.md:1).

## Data Contract

Published article JSON files must satisfy the hook contract:

- `id`
- `title`
- `source_url`
- `summary`
- `tags`
- `status`

Common fields emitted by the workflow include `source`, `url`, `collected_at`, `score`, `audience`, `relevance_score`, `category`, and `key_insight`.
