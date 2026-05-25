## 1. Implement backfill script

- [x] 1.1 Create `scripts/backfill_scores.py` with argparse CLI (`--days`, `--dry-run`, `--provider`).
- [x] 1.2 Implement article discovery: find `.json` files in `knowledge/articles/` with mtime within `--days`.
- [x] 1.3 Implement raw-item construction from existing article fields (title→title, summary→raw_description, etc.).
- [x] 1.4 Call `analyze_item()` with loaded profile for each article.
- [x] 1.5 Merge identity fields back (id, collected_at, published_at, author, source_url, url, source) and force `status: "published"`.
- [x] 1.6 Write updated JSON to same path (2-space indent, UTF-8, no ASCII escape).
- [x] 1.7 Rebuild `index.json` after all articles processed.

## 2. Error handling and logging

- [x] 2.1 Skip and log on LLM call failure (don't abort batch).
- [x] 2.2 Skip and log on file read/write failure.
- [x] 2.3 Skip and log on invalid JSON in existing article.
- [x] 2.4 Print summary stats at end (backfilled, skipped, errors).

## 3. Testing

- [x] 3.1 Add non-LLM unit test for raw-item construction logic.
- [x] 3.2 Add non-LLM unit test for identity field preservation after merge.
- [x] 3.3 Verify `uv run pytest -q -m non_llm` still passes.
- [x] 3.4 Run `--dry-run` on actual last 3 days and inspect output.
