# Design: Backfill v0.6.0 Scoring Fields

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  scripts/backfill_scores.py                          │
│                                                      │
│  1. Load relevance profile                           │
│  2. Find article files with mtime within --days      │
│  3. For each article:                                │
│     a. Construct "raw item" from existing fields:    │
│        - title → title                               │
│        - summary → raw_description                   │
│        - source_url → source_url                     │
│        - source → source                             │
│        - url → url                                   │
│     b. Call analyze_item(item, profile)               │
│        → LLM generates new summary + all v0.6.0     │
│          scoring fields                               │
│     c. Merge result into article dict:               │
│        - PRESERVE: id, collected_at, published_at,   │
│          author, url, source_url, source             │
│        - REPLACE: summary, tags, key_insight,        │
│          category, audience, score, relevance_score, │
│          status (force "published")                  │
│        - ADD: all v0.6.0 fields from analyzer output │
│     d. Write updated JSON to same file path          │
│  4. Rebuild index.json                               │
└──────────────────────────────────────────────────────┘
```

## Key design choices

### Reusing `analyze_item()` as-is

The existing `workflows/analyzer.py:analyze_item()` takes a raw item dict and a profile, calls the LLM, normalizes/clamps output, applies rule caps, and returns an enriched dict. We construct a compatible raw item from the existing article's fields and pass it through unchanged.

### Preserving identity fields

After `analyze_item()` returns, we overlay the identity fields from the original article:

```python
identity_fields = ["id", "collected_at", "published_at", "author", "source_url", "url", "source"]
for field in identity_fields:
    enriched[field] = original[field]
enriched["status"] = "published"
```

### Error handling

- LLM call failure: log error, skip article, continue (same pattern as main workflow)
- File read/write failure: log and skip
- Invalid JSON in existing article: log and skip

### Cost

~65 articles × ~1K input + ~0.5K output tokens = ~97K total tokens.
- DeepSeek/Qwen: < $0.10
- OpenAI: ~$0.50

## CLI interface

```bash
# Backfill last 3 days (default)
uv run python scripts/backfill_scores.py

# Custom range
uv run python scripts/backfill_scores.py --days 7

# Dry run (show what would be backfilled, don't write)
uv run python scripts/backfill_scores.py --dry-run

# Override LLM provider
uv run python scripts/backfill_scores.py --provider openai
```

## Dependencies

- Reuses `workflows.analyzer.analyze_item`
- Reuses `workflows.relevance_profile.load_relevance_profile`
- Reuses `scripts.build_index.build_index` / `save_index`
- No new dependencies
