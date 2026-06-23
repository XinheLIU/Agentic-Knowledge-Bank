# Changelog
> Last updated: 2026-06-23

All notable changes are listed by release. There are no `git` tags yet; older sections may name commit hashes for traceability.

## [Unreleased]

## [0.7.0] — 2026-06-23

- Externalize LLM prompts into `prompts/*.txt` (analyzer, reviewer, reviser + their system messages), loaded via `workflows/prompts.py`. A provider-specific file (`prompts/<provider>/<name>.txt`) overrides the generic one; substitution uses `string.Template` to coexist with literal JSON braces. Prompt text was extracted verbatim — pipeline behavior is unchanged.
- Add `workflows/digest.py`: a standalone CLI that reads `knowledge/articles/`, ranks the day's `study-now` / `save-for-context` items by `priority_score`, renders a grouped markdown digest, and emails it (stdlib SMTP, plain text). No-ops gracefully when SMTP env is unset.
- Wire the digest into `daily-collect.yml` as a final step, gated on the `EMAIL_ADDRESS` secret.
- Both features borrowed from the retired Info-Sentinel-Agent (`prompt_manager.py`, `notifier.py`); no new runtime dependencies added.

## [0.6.0] — 2026-05-24

- Add configurable relevance profile (`workflows/relevance_profile.yaml` + loader) with user status, focus topics (P0/P1/P2), learning tracks, source type preferences, learning tag allowlist, and negative patterns.
- Expand analyzer output with personal scoring fields: `personal_fit_score`, `technical_depth_score`, `actionability_score`, `source_credibility_score`, `novelty_score`, `priority_score`, `reading_priority`, `relevance_reason`, `suggested_action`, `confidence`, `source_type`, `learning_track`, `learning_tags`.
- Add rule caps: discussion/news without technical mechanism capped at `low-priority`; P0 match with tutorial value floored at `save-for-context`; `skip` reserved for clearly irrelevant/duplicate/broken items.
- Preserve `relevance_score` (mirrors `personal_fit_score`) and `score` (derived from `priority_score`) for backward compatibility.
- Expand tag system: separate broad tags (`tags`) from learning-intent tags (`learning_tags`); add 21 learning-intent tags to allowlist.
- Update quality scoring to 6 dimensions / 115 points: summary (25), tech depth (25), format (20), tag precision (15, split broad+learning), hollow-word (15), personal relevance (15). Grades: A (≥90), B (≥70), C (<70).
- Extend `hooks/validate_json.py` with optional validation for new enum/range fields; historical articles without new fields remain valid.
- Update reviewer to profile-aware scoring with `personal_relevance` and `actionability` dimensions replacing `relevance` and `originality`.
- Persist all new fields in organizer with safe defaults and clamping for partial LLM output.
- Add `docs/personal-knowledge-strategy-plan.md` strategy document.

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
