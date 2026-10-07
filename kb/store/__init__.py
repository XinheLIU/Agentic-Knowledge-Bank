"""Canonical SQLite asset store (ticket 07).

The only persistence contract for accepted assets, admission records, runs,
tags, story edges, localized artifacts, and full-text retrieval. Modules:

- :mod:`kb.store.schema`  — versioned, transactional, repeatable migrations.
- :mod:`kb.store.writer`  — write-once items, append-only admissions, runs.
- :mod:`kb.store.reader`  — accepted-only default reads + explicit audit paths.
- :mod:`kb.store.fts`     — FTS5 search with CJK probe and tested fallback.
- :mod:`kb.store.export`  — JSONL export / restore + consistent backup.
- :mod:`kb.store.model`   — the typed ``AssetStore`` facade.

No UI, MCP, digest, or Horizon transport logic may enter these modules.
"""
