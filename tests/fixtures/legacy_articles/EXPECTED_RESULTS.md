# Cutover fixture corpus — expected mapped / search results

> Last updated: 2026-09-12

Ticket: `04-create-cutover-baseline` (revised after verifier findings) · Baseline date:
2026-09-11 · Source: production `knowledge/articles/` at commit `6054488` (v0.7.0).
**Read-only derivation**: the live corpus was never modified, archived, or deleted;
`tests/fixtures/legacy_articles/` holds sanitized structural copies only.

## 0. Sanitization policy (revised)

- Article fixtures are **sanitized structural copies**: they preserve every schema
  characteristic (record shape, ID regime, enum values, nullability, status/score
  coverage, legacy IDs, `source_url`/`url` for lineage and dedup testing), but all
  human-authored and user-identifying content is replaced with **deterministic
  synthetic equivalents**: `title`, `author`, `summary`, `description`,
  `raw_description`, `key_insight`, and `relevance_reason` are regenerated per record
  (`Sanitized … fixture content for legacy record <id>.`, author
  `fixture-author-<id>`) with null/non-null shape preserved exactly. They are
  **not** byte-identical to production — sanitization and byte identity are
  contradictory. Lineage is proven by `inventory.json`, which records per-fixture
  `source_file`, `source_id`, and the SHA-256 of the production original.
- `skipped_records.jsonl` and `raw/` are **fully synthetic minimal representatives**:
  they reproduce only the structural variants (stages, reason families, ID-break
  regimes, collector record shape) with `example.com` URLs and no real user content.
- Regression tests assert no fixture content field equals its production source value
  (non-null author/title/summary/body), no Reddit user content, and that identity
  (`id`) plus source URL lineage are unchanged.

## 1. Corpus composition (production facts the fixtures must represent)

Full production corpus at baseline:

| Characteristic | Value | Evidence |
|---|---|---|
| `*.json` files in `knowledge/articles/` (incl. `index.json`) | 625 | glob count |
| Article records (excl. `index.json`) | 624 | glob count |
| Files with colon IDs (`rss:*`) | 406 (65.1%) | discovery G1 |
| Statuses | 540 `published`, 84 `review` | glob scan |
| Distinct record schemas | 4 record shapes (16/17/29/31 keys) + 1 list file (`index.json`) | 16-key / 17-key(+`updated_at`) / 29-key(v0.6 scores) / 31-key(+`description`,`raw_description`) |
| Duplicate URLs within published corpus | 0 | URL scan (Organizer deduped on `source_url`) |
| `_skipped.jsonl` records | 77 (75 analyzer, 2 organizer) | line count |
| Duplicate URLs inside `_skipped.jsonl` | 10 URLs, 65 extra rows | URL scan (repeat captures of same story) |
| URLs skipped then later published | 8 | URL cross-join |
| `raw/` snapshots | 4 (`raw_20260502_135323.json` … `raw_20260505_100704.json`, list-of-item-records) | glob scan |

The 20-article fixture corpus below reproduces **every** distinct record schema, every
`source_type` value, all three `reading_priority` values, seven null-author records, and
the colon-ID / colon-free ID split — with all human-authored content replaced by
deterministic synthetic equivalents (§0).

## 2. Fixture article coverage (20 records)

`tests/fixtures/legacy_articles/articles/*.json` (filenames are the production source
names recorded in `inventory.json`; each record's `id` equals its filename stem):

| Fixture record | Schema | Colon ID | source_type | reading_priority | Represents |
|---|---|---|---|---|---|
| `github-20260502-021..023` (3) | 16-key minimal | no | — | — | oldest minimal schema; `status=review`; non-null author |
| `github-20260507-001/002` (2) | 17-key +`updated_at` | no | — | — | mid-generation schema |
| `github-20260530-001` | 29-key v0.6 | no | repository | study-now | full v0.6 personalization fields; colon-free |
| `hn-best-20260518-002/003` (2) | 16-key (+`updated_at` variant) | no | — | — | `author=null`; `status=published` |
| `reddit-localllama-20260513-001` | 16-key +`updated_at` | no | — | — | LocalLLaMA source, colon-free RSS-slug ID |
| `rss:armin-ronacher-20260522-015` | 31-key | yes | blog | study-now | richest schema incl. `description`/`raw_description` (MCP G7 fields) |
| `rss:arxiv-cs-ai-20260522-005` | 31-key | yes | paper | study-now | arXiv paper variant |
| `rss:deepmind-blog-20260609-006` | 29-key | yes | blog | low-priority | lowest score (3) in corpus sample |
| `rss:fabien-sanglard-20260608-008` | 29-key | yes | tutorial | save-for-context | tutorial variant |
| `rss:hacker-news-best-20260524-002` | 31-key | yes | benchmark | save-for-context | benchmark variant |
| `rss:hacker-news-best-20260525-002` | 29-key | yes | news | save-for-context | news variant |
| `rss:hacker-news-best-20260606-002` | 29-key | yes | discussion | save-for-context | discussion variant |
| `rss:mitchell-hashimoto-20260530-010` | 29-key | yes | blog | save-for-context | the canonical colon-ID example cited in discovery G1 |
| `rss:reddit-r-machinelearning-20260519-005/013` | 17-key | yes | — | — | colon ID on mid schema; 013 has corpus-max score 9 |
| `rss:simon-willison-20260528-008` | 31-key | yes | documentation | study-now | documentation variant |

Variant tallies: colon IDs **11/20**, colon-free **9/20** · `source_type` present on 12/20
(all 8 enum values seen: repository, blog, paper, tutorial, benchmark, news, discussion,
documentation) · `reading_priority` study-now 6, save-for-context 4, low-priority 1,
absent 9 · `author=null` on 7/20 · `status` published 16, review 4 · `description`/
`raw_description` present on 3/20.

## 3. Skipped records fixture (`skipped_records.jsonl`, 5 rows — smallest full variant cover)

Fully sanitized synthetic rows (`example.com` URLs only). Each structural variant
appears exactly once (the two organizer rows pair one variant reason with the two ID
regimes):

| Stage | Reason family | Rows | ID regime represented |
|---|---|---|---|
| analyzer | `relevance_score 0.3 < threshold 0.4` (current threshold) | 1 | collector-style `reddit-ml-*` ID — G2 break (never equals published `rss:*` ID) |
| analyzer | `relevance_score 0.0 < threshold 0.5` (early threshold) | 1 | `"id": "unknown"` — analyzer could not attribute the item |
| analyzer | `relevance_score 0.15 < threshold 0.4` | 1 | colon-style `rss:example-feed-*` ID |
| organizer | `schema validation failed: missing key_insight` | 2 | colon-style `rss:*` and colon-free `github-*` — both dropped pre-publish |

## 4. Raw snapshot fixture (`raw/raw_sanitized_sample.json`, 1 file, 3 records)

Sanitized minimal representative of the collector-stage record shape (fields `id`,
`title`, `source`, `source_url`, `author`, `published_at`, `raw_description`, `stars`,
`language`, `topics`, `collected_at`): one GitHub record, one RSS record with author,
one RSS record with `author=null`. Represents the collect-time ID namespace (G2's
"collect-time ID") that differs from published IDs. No production content.

## 5. Expected legacy→canonical identity mapping

Canonical identity follows ticket 02 / ADR 0001: **the legacy import adapter mints
`legacy:<opaque legacy id>` exactly once** (e.g. `legacy:rss:mitchell-hashimoto-20260530-010`).
The raw legacy id is *not* treated as already-canonical, and no stage re-derives,
re-slugs, or renames it. Mapping rules:

```
canonical id   = "legacy:" + legacy id (verbatim, colons preserved)
legacy_url     = record["source_url"]  (== record["url"] for all 20 fixtures)
author         = record["author"]      (null → SQL NULL, never "")
source_type    = record["source_type"] (absent → NULL, never a fabricated default)
content_main   = record["description"] or record["raw_description"] (else NULL)
personalization fields (14 fields) → dropped, no canonical column (R-D7)
```

Expected mapping outcomes for the fixture set (asserted against the static oracle
`expected_mapped.jsonl`):

- 20/20 records map 1:1 to a canonical asset minted as `legacy:<legacy id>`.
- 11/20 minted IDs contain `:` twice (`legacy:rss:...`) and must be accepted by the
  new store's colon-legal ID rule while `validate_json.py` rejects the legacy id.
- `author=null` on 7 records → canonical `author` NULL.
- `source_type` absent on 10/20 → canonical `source_type` NULL.
- `content_main` non-NULL only for the 3 `description` carriers → NULL otherwise.
- The 14 personalization fields appear in no mapped row.

## 6. Expected search results (static oracle `expected_search.json`)

The oracle pins results using the legacy MCP ranking (keyword in title ×10, in summary
×3, + `relevance_score`×2; higher first; NULL relevance = 0) over the 20-article corpus,
with **minted canonical IDs** in results:

| Query | Expected hits (minted ids, ranked) | Why |
|---|---|---|
| `sanitized` | all 20 fixture ids; top = `legacy:rss:reddit-r-machinelearning-20260519-013` | every sanitized title/summary carries the token; 013 wins the 0.95×2 relevance bonus (tie with `…-005` at 14.9 broken by id ordering) |
| `legacy record rss:mitchell-hashimoto-20260530-010` | `legacy:rss:mitchell-hashimoto-20260530-010` | per-record synthetic token |
| `legacy record github-20260502-021` | `legacy:github-20260502-021` | per-record synthetic token |
| `zzz-no-match-token` | none | empty-result guard |

`expected_search.json` also pins the sanity floor (the `sanitized` query must never
be empty) and the corpus-max relevance top hit. Tests compare the implementation-like
`implementation_search_hits()` against this static file — the oracle is data, not
re-derived at test time.

## 7. Verification contract for this corpus

`tests/test_legacy_fixture_corpus.py` (marked `non_llm`) pins:

1. inventory counts: 20 articles, 5 skipped rows, 1 raw snapshot, all file checksums
   match `inventory.json` (immutability); baseline counts (625/624/406/77/4) recorded;
2. provenance: every article fixture records `source_file` + `source_id` +
   `source_sha256` matching the live production original, and keeps the source
   record's `id` and `source_url` (structural lineage without byte-identity claims);
3. **sanitization regression**: for every fixture, non-null `title`/`author`/
   `summary`/`description`/`raw_description`/`key_insight`/`relevance_reason` all
   differ from the production source values (author is the synthetic
   `fixture-author-<id>`), while `id`, `source_url`, key sets, null shape, and
   status/score/enum coverage are unchanged; no fixture carries Reddit user content;
4. coverage invariants: 4 article record shapes (16/17/29/31 keys) plus the index
   list-file shape in production, colon-ID presence, the G1 example ID,
   null-author records, every `source_type` enum value, all three `reading_priority`
   values, `description` carriers;
5. G1 reproduction: exactly the 11 colon-ID fixtures fail `hooks/validate_json.py`'s ID
   rule while all 20 pass every other structural rule and the canonical ID rule;
6. skip log invariants: all stage/reason/ID-regime variants in 5 rows; G2 orphan IDs;
7. static-oracle determinism: `map_legacy_article()` (minted `legacy:` ids, NULL
   propagation, drop-list) equals `expected_mapped.jsonl` for every fixture, and
   `implementation_search_hits()` equals `expected_search.json` for every query.
