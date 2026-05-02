# Changelog

All notable changes to this project are listed by release. Version numbers are chronological milestones aligned with git history (there are no `git` tags yet); each section names the commit hash for traceability.

## [0.4.0] — 2026-05-02

- Add `mcp_knowledge_server.py`: zero-dependency MCP Server with 3 tools (`search_articles`, `get_article`, `knowledge_stats`) for searching local knowledge base.
- Add MCP config files for OpenCode (`opencode.json`), Claude Code (`.claude/mcp.json`), and Codex (`.codex/mcp.json`).
- Document MCP usage and configuration in `AGENTS.md`.

## [0.3.0] — 2026-05-02

**Commit:** `85b256b`

- Add `pyproject.toml` and uv-friendly dependencies (`feedparser`, `pytest`, etc.).
- Introduce the Python pipeline package (`pipeline/`: RSS reader, LLM client, four-step orchestration) plus `scripts/` shims for older entry paths.
- Refactor RSS collection to use **feedparser** instead of regex.
- Switch default LLM provider from **DeepSeek** to **Qwen**; expand `.env.example` for all supported providers.
- Add **pytest** coverage for `model_client`, `rss_reader`, `pipeline`, and hooks; ship `tests/fixtures/articles/example-published.json`.
- Stop tracking generated knowledge JSON in git: use `.gitkeep` under `knowledge/articles` and `knowledge/raw`, remove sample bulk data from the tree.
- Expand `AGENTS.md` (CLI reference, updated project layout).

## [0.2.0] — 2026-05-02

**Commit:** `0468882`

- Add OpenCode write hook plugin `.opencode/plugins/validate.ts` (runs validation on article writes).
- Add Python quality gate scripts: `hooks/validate_json.py` (schema) and `hooks/check_quality.py` (scoring).
- Document hook behavior in `spec/hooks-spec.md`.

## [0.1.0] — 2026-05-02

**Commit:** `5cda678`

- Bootstrap **AI Knowledge Base**: vision, specs (`spec/`), and `AGENTS.md` project guide.
- Add OpenCode **agents** (collector, analyzer, organizer) and **skills** (GitHub Trending, Hacker News, arXiv, tech summary, markdown writer, metrics, etc.).
- Seed sample **knowledge** outputs (`knowledge/raw`, `knowledge/articles`, `index.json`) and project scaffolding (`.env.example`, `.gitignore`).