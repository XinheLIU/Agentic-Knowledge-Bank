# Proposal: Backfill v0.6.0 Scoring Fields

> Status: proposed

## Problem

All 292 existing articles in `knowledge/articles/` lack the v0.6.0 personal relevance scoring fields (`personal_fit_score`, `reading_priority`, `learning_tags`, etc.). The new scoring and tagging system has never been run against real content.

## Scope

Backfill the most recent 3 days of articles (~65 files, May 22–24 content) by re-running them through the Analyzer LLM prompt with the current relevance profile, then overwriting the files in-place.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Article IDs | Keep original — no ID regeneration |
| 2 | `collected_at` | Keep original timestamp |
| 3 | `status` | Keep `"published"` (not `"review"`) |
| 4 | Summary regeneration | Accept — LLM regenerates from existing summary as input, new prompt is profile-aware |
| 5 | Scope | 3 days only (May 22–24), ~65 articles |
| 6 | Implementation | Standalone script `scripts/backfill_scores.py` |

## Out of scope

- Backfilling older articles (can be done later by changing `--days`)
- Changing the main workflow graph
- Adding a backfill CLI flag to `workflows/graph.py`

## Success criteria

- All targeted articles have complete v0.6.0 fields after backfill
- Existing `id`, `collected_at`, `published_at`, `author` fields are preserved
- `status` remains `"published"`
- `index.json` is rebuilt after backfill
- Non-LLM tests still pass
