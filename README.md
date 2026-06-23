# AI Knowledge Base

> Last updated: 2026-06-23  
> 中文: [README.zh-CN.md](README.zh-CN.md)

Automated technical intelligence for AI, LLM, RAG, and agent tooling. Version **0.7.0** runs a LangGraph workflow under `workflows/` that collects GitHub and RSS sources, analyzes each item with an LLM, reviews quality in a loop, and writes structured JSON articles to `knowledge/articles/`. A standalone digest CLI then emails the day's high-priority reading.

## How It Works

```text
plan → collect → analyze → review
                          ├─ pass → organize → END (rebuild index.json)
                          ├─ fail & iterations left → revise → review
                          └─ fail & max iterations → human_flag → END
```

- **Planner** — per-run strategy (limits, thresholds).
- **Collector** — GitHub Search API + RSS (`workflows/rss_sources.yaml`).
- **Analyzer / Reviewer / Reviser** — LLM analysis, five-dimension weighted review, targeted revision. Prompt text lives in `prompts/` (loaded via `workflows/prompts.py`), not inline in the nodes.
- **Organizer** — dedupe by `source_url`, write `knowledge/articles/<slug>-<YYYYMMDD>-<NNN>.json`.
- **HumanFlag** — batches that exhaust the review loop go to `knowledge/pending_review/` (local only, not committed by CI).

Skipped or filtered items are audited in `knowledge/articles/_skipped.jsonl` (one JSON object per line: id, source, reason).

## Project Layout

```text
ai-kb/
├── workflows/               # LangGraph nodes, state, graph CLI, RSS config
│   ├── prompts.py           # Prompt template loader (provider override → generic)
│   └── digest.py            # Daily digest builder + email sender (stdlib SMTP)
├── prompts/                 # Externalized prompt templates (*.txt)
├── scripts/
│   └── build_index.py       # Rebuild knowledge/articles/index.json from disk
├── hooks/                   # JSON schema + quality scoring
├── tests/                   # pytest (non_llm / llm_e2e)
├── notebooks/               # LangGraph demo notebook
├── knowledge/
│   ├── articles/            # Published JSON + index.json + _skipped.jsonl
│   └── pending_review/      # Failed review-loop batches
├── ui/                      # Notion-like local management panel (Flask)
├── mcp_knowledge_server.py  # MCP search over articles (stdio JSON-RPC)
├── openspec/                # Change proposals and capability specs
├── .github/workflows/       # daily-collect.yml, llm-e2e.yml
└── AGENTS.md                # Maintainer guide (structure, conventions, CLI)
```

## Setup

```bash
uv sync
cp .env.example .env
```

Configure as needed:

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub Search API (public repos) |
| `LLM_PROVIDER` | `qwen` (default), `deepseek`, or `openai` |
| `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | Provider API keys |

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
uv run python -m workflows.graph --sources github,rss --limit 20 --json
```

After a non–dry-run completes, the graph **rebuilds** `knowledge/articles/index.json` from all article files (derived artifact, not incrementally patched during organize).

Rebuild the index manually:

```bash
uv run python scripts/build_index.py
uv run python scripts/build_index.py --dry-run
```

## Browse & Edit (UI)

```bash
uv pip install -r ui/requirements.txt
uv run python ui/app.py
```

Open http://localhost:5050 — list, filter, search, edit, and batch-update articles. See [ui/README.md](ui/README.md).

## MCP Server

Expose the local knowledge base to agents (Cursor, Claude Code, Codex, OpenCode):

```bash
uv run python mcp_knowledge_server.py
```

Tools: `search_articles`, `get_article`, `knowledge_stats`. Wire-up examples live in `opencode.json`, `.claude/mcp.json`, and `.codex/mcp.json`.

## Scheduled Runs

GitHub Actions ([`.github/workflows/daily-collect.yml`](.github/workflows/daily-collect.yml)) runs daily (UTC 08:00):

```bash
uv run python -m workflows.graph --sources github,rss --limit 20 --verbose
```

- Commits new files under `knowledge/articles/` only (not `pending_review/`).
- Validates **newly staged** article JSON with hooks before push.
- `human_flag` emits a workflow warning locally/CI; use `--fail-on-human-flag` when you want a hard exit.

Real-provider E2E tests run separately in [`.github/workflows/llm-e2e.yml`](.github/workflows/llm-e2e.yml).

## Email Digest

After a run, email yourself a ranked digest of the day's `study-now` / `save-for-context` items (read from `knowledge/articles/`, grouped by priority, sorted by `priority_score`):

```bash
uv run python -m workflows.digest --stdout            # preview, no email
uv run python -m workflows.digest --since 2026-06-23  # send for a given day
```

Configure SMTP via env (the digest no-ops gracefully when these are unset):

| Variable | Purpose |
|----------|---------|
| `EMAIL_ADDRESS` | Sender address (enables sending) |
| `EMAIL_PASSWORD` | Sender password / app password |
| `SMTP_HOST` / `SMTP_PORT` | Defaults `smtp.gmail.com` / `587` |
| `DIGEST_RECIPIENTS` | Comma-separated recipients (defaults to sender) |

The daily CI workflow sends the digest automatically when `EMAIL_ADDRESS` is set as a repo secret.

## Validate Articles

```bash
uv run python hooks/validate_json.py tests/fixtures/articles/example-published.json
uv run python hooks/check_quality.py tests/fixtures/articles/example-published.json
```

For on-disk articles (exclude `index.json`):

```bash
uv run python hooks/validate_json.py knowledge/articles/github-*.json
uv run python hooks/check_quality.py knowledge/articles/github-*.json
```

OpenCode can also run validation on write via `.opencode/plugins/validate.ts`.

## Data Contract

**File naming:** `knowledge/articles/{source-slug}-{YYYYMMDD}-{NNN}.json`  
**ID:** same as basename without `.json`; pattern `^[a-z0-9-]+-\d{8}-\d{3}$` (lowercase slug, no colons).

**Required fields** (enforced by `hooks/validate_json.py`):

- `id`, `title`, `source_url`, `url`, `summary`, `tags`, `status`
- `key_insight`, `category` (single enum value), `relevance_score` (0–1)

**Nullable when unknown:** `author`, `published_at` — use JSON `null`, not source-name or collection-time placeholders.

**Common optional fields:** `source`, `collected_at`, `score`, `audience`, `published_at`, `author`.

**Index:** `knowledge/articles/index.json` — compact list (`id`, `title`, `source`, `source_url`, `category`, `relevance_score`) rebuilt from articles; not validated as an article file.

Fixture reference: [tests/fixtures/articles/example-published.json](tests/fixtures/articles/example-published.json).

## Development

```bash
uv run pytest -q -m non_llm
uv run python -m compileall workflows hooks scripts mcp_knowledge_server.py
```

### Testing

| Marker | Purpose |
|--------|---------|
| `non_llm` | Deterministic tests (mocked / no live LLM) |
| `llm_e2e` | Real provider workflow verification (needs API keys) |

```bash
uv run pytest -q -m non_llm
uv run pytest -q -m llm_e2e
```

## Further Reading

- [AGENTS.md](AGENTS.md) — conventions, workflow rules, agent-oriented CLI reference
- [CHANGELOG.md](CHANGELOG.md) — release history
- [project-vision.md](project-vision.md) — original scope and go/no-go criteria
- [docs/archive/](docs/archive/) — historical audits and strategy memos (2026-05)
