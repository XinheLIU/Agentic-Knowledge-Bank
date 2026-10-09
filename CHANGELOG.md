# Changelog
> Last updated: 2026-10-09

All notable changes are listed by release. There are no `git` tags yet; older sections may name commit hashes for traceability.

## [Unreleased]

- Retire the legacy LangGraph/JSON production path (ticket 16): delete `workflows/`, `hooks/`, `prompts/`, `scripts/build_index.py`, `scripts/backfill_scores.py`, the LangGraph demo notebook, `.opencode/plugins/validate.ts`, `.env.example`, and the `llm-e2e.yml` CI lane; drop the `langgraph`/`feedparser` dependencies. The sanitized legacy fixture corpus (`tests/fixtures/legacy_articles/`) is retained as the migration oracle.
- Evict the Horizon *run* surface from KB (workspace refactor): delete the `kb/horizon/` provider shims (`adapter.py`, `transport.py`, `source_config.py`), the `scripts/production_run.py` / `scripts/setup_horizon.py` launchers, `kb.ingest.ingest_horizon_run`, the `kb.cli` information-command forwarding, and the run/digest summary types. Provider communication and setup live in `agent-tools`; run orchestration, scheduling and digests live in Information Assistant. KB keeps asset identity, the pure mapper, admission and storage, and admits a completed provider payload through `kb.ingest.ingest_horizon_payload`.
- Move the KB runtime surface into Information Assistant (wiki repositioning): `kb/`, `ui/` and `mcp_knowledge_server.py` travel by working-tree copy — so the uncommitted edits in `kb/` are preserved — together with the eight KB test modules, `tests/conftest.py`, the `horizon-profiles` / `horizon` / `legacy_articles` fixture sets (the legacy fixture corpus moves but is flagged for pruning there), `docs/product/ai-kb/`, `docs/adr/0001-radar-minted-immutable-item-ids.md` and `docs/personal-knowledge-strategy-plan.md`. AKB's `pyproject.toml` is reduced to a harness around `scripts/export-skills.py`; the `ai-kb` path dependency is replaced by local packaging in Information Assistant, whose version source (`kb.store.model.project_version`) now resolves the `information-assistant` distribution with `ai-kb` as a legacy fallback.
- Delete `docs/export-contract.md` and `docs/installed-skill-migration.md` — byte-identical copies already live in Information Assistant. Delete `tests/test_legacy_retirement.py` and `tests/test_project_memory.py` as completed-migration receipts: their subjects either moved or were rewritten.
- Delete the unrelated legacy: `.opencode/` (retired-pipeline agents, 13 non-KB skills, `node_modules`), `opencode.json`, the repo-local `openspec-*` copies under `.claude/` and `.codex/`, the broken MCP configs, `patterns/`, `.rehearsal-tmp/`, `docs/archive/`, `docs/pre-split-instructions.md`, `docs/sibling-repo-failures.md` and `TODO.md` (its 认知复合引擎 epic and 泛读/精读 model extracted first into `docs/compounding/draft.md` for step 2). `docs/exec-plans/workspace-refactor.md` folds into `docs/exec-plans/wiki-repositioning.md`, which is now the single execution plan.
- Cut the skill set to the four the destination needs (`map-materials`, `clean-notes`, `llm-wiki-ingest`, `llm-wiki-lint`): delete `organize-docs` and `llm-wiki-init`, move `archive-materials` to Writing Assistant, and regenerate the discovery links from `catalog/` rather than editing the symlinks.
- Freeze the knowledge model in `docs/knowledge-model.md` and rewrite the four skills against it: stage 0 inventories a read-only external archive into `materials.md`; stage 1 restructures it into MECE `notes/`; stage 2 writes L1–L4 concept pages against a narrative gate and a verified `sources.md`; lint audits the result read-only. Record the two hard-to-reverse decisions as ADR [0002](docs/adr/0002-external-read-only-archive.md) and [0003](docs/adr/0003-provenance-and-trust-separate-files.md).
- Phase C Transformer test run passed every structural acceptance criterion: all four level sections on all 7 pages (18 full / 9 partial / 0 stub / 1 named gap), 353 footnotes resolving, every `ext:` id verified with a pinned version, all 41 `materials.md` sha256 values matching the archive, and the main narrative surviving a side-by-side read against the 119-page plain-LLM-Wiki baseline.

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
- Refresh README / `README.zh-CN.md`; remove root `spec/`; add a local Markdown spec archive. Historical release notes above the cutover describe the retired pipeline and are preserved verbatim.
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
