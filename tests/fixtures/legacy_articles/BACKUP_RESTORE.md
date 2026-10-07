# Backup / export / restore / checksum / row-count procedure for the Horizon cutover

> Last updated: 2026-09-12

Ticket 04 — cutover baseline. Read-only with respect to production data: every command
here either reads `knowledge/` or writes into a backup target outside production
paths. Run from the repository root. Do NOT run the destructive recovery commands
unless the cutover rehearsal (ticket 14) calls for them.

Conventions
-----------
- `STAMP`  : UTC timestamp, `$(date -u +%Y%m%dT%H%M%SZ)` — use ONE stamp per run
             so manifest, checksums and logs line up.
- `BACKUP` : backup root, default `.scratch/horizon-kb-design/backups/$STAMP`.
             Never inside `knowledge/` (production paths must stay pristine).
- Checksums: SHA-256, one line per file, `<sha256>  <relative-path>` — paths are
             relative to `$BACKUP` so verification runs FROM INSIDE `$BACKUP`.
- Row counts: articles = number of `*.json` records in `articles/` excluding
             `index.json`; skipped = line count of `_skipped.jsonl`;
             raw = number of `raw_*.json` snapshots.
- Baseline : the production baseline this backup must reproduce is recorded in
             `tests/fixtures/legacy_articles/inventory.json`
             (`production_baseline`) — articles incl. index = 625, article records
             = 624, colon-ID records = 406, skipped rows = 77, raw snapshots = 4.

0. Freeze (preconditions — all read-only checks)
------------------------------------------------
    git status --porcelain               # must be clean or understood; record output
    git rev-parse HEAD                   # record baseline commit
    ls knowledge/articles/*.json | wc -l # record total file count (incl. index.json)

1. Backup (non-destructive copy)
--------------------------------
    STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    BACKUP=".scratch/horizon-kb-design/backups/$STAMP"
    mkdir -p "$BACKUP"
    cp -R knowledge "$BACKUP/knowledge"
    git rev-parse HEAD > "$BACKUP/BASELINE_COMMIT.txt"
    git status --porcelain > "$BACKUP/GIT_STATUS.txt"

2. Manifest + checksums (paths relative to $BACKUP)
---------------------------------------------------
    ( cd "$BACKUP" && find knowledge -type f | sort | xargs shasum -a 256 ) \
        > "$BACKUP/SHA256SUMS.txt"
    cat "$BACKUP/SHA256SUMS.txt" | head -3   # sanity: relative paths, no leading '/'
    python3 - "$BACKUP" <<'PY' > "$BACKUP/MANIFEST.txt"
import glob, json, os, sys
backup = sys.argv[1]
art = [p for p in glob.glob(f"{backup}/knowledge/articles/*.json")
       if os.path.basename(p) != "index.json"]
skipped = f"{backup}/knowledge/articles/_skipped.jsonl"
raw = glob.glob(f"{backup}/knowledge/raw/raw_*.json")
print(f"article_files_including_index:{len(glob.glob(f'{backup}/knowledge/articles/*.json'))}")
print(f"articles:{len(art)}")
print(f"skipped_rows:{sum(1 for l in open(skipped) if l.strip()) if os.path.exists(skipped) else 0}")
print(f"raw_snapshots:{len(raw)}")
PY
    cat "$BACKUP/MANIFEST.txt"

3. Row-count + checksum verification (must pass before cutover)
---------------------------------------------------------------
Checksums must be verified against the BACKUP copy, not the live tree — run from
inside `$BACKUP` so the relative paths in `SHA256SUMS.txt` resolve there:

    cd "$BACKUP" && shasum -a 256 --check SHA256SUMS.txt && cd -   # all OK, exit 0

Row counts are compared against the baseline:

    cat "$BACKUP/MANIFEST.txt"
    # Must equal the baseline in tests/fixtures/legacy_articles/inventory.json:
    #   article_files_including_index=625, articles=624, skipped_rows=77, raw_snapshots=4.
    # (If the live corpus legitimately grew since baseline, re-baseline inventory.json
    #  first; a mismatch without re-baselining aborts cutover.)

4. JSONL export (portable, diff-able snapshot of the canonical store)
--------------------------------------------------------------------
After the SQLite store exists (ticket 07), export BEFORE the cutover window:

    uv run python -m kb.store export --format jsonl \
        --output "$BACKUP/assets-$STAMP.jsonl"
    wc -l "$BACKUP/assets-$STAMP.jsonl"              # == exported row count
    shasum -a 256 "$BACKUP/assets-$STAMP.jsonl"      # pin export checksum too

If only the legacy JSON corpus is being exported (no store yet), the backup in step 1
is already the export; optionally flatten it:

    python3 - "$BACKUP" <<'PY'
import glob, json, os, sys
backup = sys.argv[1]
out = f"{backup}/legacy-articles.jsonl"
n = 0
with open(out, "w", encoding="utf-8") as dst:
    for p in sorted(glob.glob(f"{backup}/knowledge/articles/*.json")):
        if os.path.basename(p) == "index.json":
            continue
        with open(p, encoding="utf-8") as src:
            dst.write(json.dumps(json.load(src), ensure_ascii=False) + "\n")
        n += 1
print(f"exported_rows:{n}")
PY
    wc -l "$BACKUP/legacy-articles.jsonl"            # must equal articles:NNN above

5. Restore (rollback; destructive — only for rehearsal/recovery)
----------------------------------------------------------------
Restore swaps the backup copy back into place. It overwrites production data and must
never run while the pipeline or UI is writing:

    # 5a. Stop writers (automation / UI / digest) first.
    # 5b. Verify the BACKUP checksums again — from inside $BACKUP:
    cd "$BACKUP" && shasum -a 256 --check SHA256SUMS.txt && cd -
    # 5c. Move the current (broken/post-cutover) state aside, then restore:
    mv knowledge "knowledge.postrestore-discard-$STAMP"   # keep for forensics
    cp -R "$BACKUP/knowledge" knowledge
    # 5d. Re-verify in place (explicit post-restore verification): checksum the
    # restored tree against the same relative-path manifest, from inside $BACKUP:
    ( cd "$BACKUP" && shasum -a 256 --check SHA256SUMS.txt )
    # then confirm the restored production tree matches the backup, row for row:
    diff -r "$BACKUP/knowledge" knowledge                 # must report no differences
    # and re-state the row counts of the restored tree:
    ls knowledge/articles/*.json | wc -l                  # 625 incl. index.json
    python3 - <<'PY'
import glob, os
art = [p for p in glob.glob("knowledge/articles/*.json") if os.path.basename(p) != "index.json"]
skipped = "knowledge/articles/_skipped.jsonl"
print(f"articles:{len(art)}")
print(f"skipped_rows:{sum(1 for l in open(skipped) if l.strip()) if os.path.exists(skipped) else 0}")
print(f"raw_snapshots:{len(glob.glob('knowledge/raw/raw_*.json'))}")
PY
    # Counts must equal MANIFEST.txt / baseline before declaring recovery complete.

For the SQLite asset store, restore is the reverse of step 4:

    cp "$BACKUP/knowledge/kb.sqlite" knowledge/kb.sqlite    # binary restore (if kept)
    # and/or replay the text snapshot:
    uv run python -m kb.store restore --format jsonl --input "$BACKUP/assets-$STAMP.jsonl"
    uv run python -m kb.store stats                          # row counts must match

6. Post-restore acceptance (rehearsal exit criteria)
----------------------------------------------------
    ( cd "$BACKUP" && shasum -a 256 --check SHA256SUMS.txt )   # exit 0
    diff -r "$BACKUP/knowledge" knowledge                       # no differences
    MANIFEST counts == baseline counts (articles/skipped/raw)
    uv run pytest -q tests/test_legacy_fixture_corpus.py        # fixture corpus intact

Failure of any checksum or row-count check aborts cutover/recovery — never proceed
with a partial restore.
