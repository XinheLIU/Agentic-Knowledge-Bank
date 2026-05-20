# Changelog
> Last updated: 2026-05-19

All notable changes are listed by release. There are no `git` tags yet; older sections may name commit hashes for traceability.

## [Unreleased]

## [0.5.1] — 2026-05-19

- Unify `knowledge/articles/` on v0.5 schema: slug-based IDs, derived `index.json` (`scripts/build_index.py`), `_skipped.jsonl` audit log, nullable `author` / `published_at`.
- Tighten workflow validation (RSS `slug`, `hooks/validate_json.py`, `workflows/skipped.py`); refresh README / `README.zh-CN.md`; remove root `spec/`; add `docs/archive/` and OpenSpec cleanup archive.
- Daily CI: validate only newly staged articles; stop committing `knowledge/raw/`.

## [0.5.0] — 2026-05-06

- Replace `pipeline/` with LangGraph `workflows/` (`plan → collect → analyze → review → organize`, `human_flag` fallback).
- Add `knowledge/pending_review/`, RSS config in `workflows/rss_sources.yaml`, pytest `non_llm` / `llm_e2e` lanes, GitHub Actions LangGraph daily collect.

## [0.4.0] — 2026-05-02

- Add `mcp_knowledge_server.py` and MCP configs for OpenCode, Claude Code, Codex.

## [0.3.0] — 2026-05-02

- Add `pyproject.toml`, uv deps, `pipeline/` + feedparser RSS, default LLM provider Qwen, pytest + fixtures.

## [0.2.0] — 2026-05-02

- Add OpenCode validate hook plugin and `hooks/validate_json.py` + `hooks/check_quality.py`.

## [0.1.0] — 2026-05-02

- Bootstrap project: vision, `AGENTS.md`, OpenCode agents/skills, sample knowledge layout.
