# Canonical asset and audit model

> Last updated: 2026-09-13
> Status: **Accepted** · Date: 2026-09-12 · Owner: ticket [02](../../../.scratch/horizon-kb-design/issues/02-lock-canonical-asset-and-audit-model.md)
> Inputs: [`docs/product/ai-kb/design.md`](design.md) §2/§4 · [`admission-policy.md`](admission-policy.md) (ticket 03, normative for decision semantics) · [`horizon-contract-596e2b1.md`](../../../.scratch/horizon-kb-design/research/horizon-contract-596e2b1.md) · [`CONTEXT.md`](../../../CONTEXT.md)
> Decision record: [ADR 0001 — radar-minted immutable item IDs](../../adr/0001-radar-minted-immutable-item-ids.md)
> This artifact refines design.md; where they conflict, this document wins for identity, state, audit, and vocabulary ownership. Decision semantics (outcomes, reason codes, evidence) follow `admission-policy.md`; this document owns the storage and audit representation.

---

## 1. Identity: candidates vs assets (criterion 1)

### 1.1 One identity string, two lifecycles

The canonical ID is minted **exactly once**, in `kb/horizon/mapper.py`, as `<radar>:<opaque Horizon id>` (e.g. `horizon:github:trending:org/repo#123`). Horizon's `ContentItem.id` is opaque (`src/models.py:10-46` — the `{source}:{subtype}:{native_id}` format is an unvalidated comment), so the mapper treats it as an opaque string and namespaces it by radar exactly once. No later stage mints, renames, or re-derives it. Colons are legal; the legacy validator's no-colon rule is retired with the legacy path (ticket 16, closing G1). This is the single rule that kills G2: there is no second ID allocation point.

The same string names **two distinct things**, which must never be conflated (this separation is what fixes the UNIQUE-url contradiction):

- **Candidate** — one fetched occurrence of an item in one run. Identified by `(run_id, item_id)`. Lives in the **admission ledger**. A rejected or failed candidate has **no** row in `items`. The same Horizon id re-fetched in a later run is a *new candidate*.
- **Asset** — a candidate that has been **accepted** and persisted. Identified by `item_id` in `items` ("knowledge asset" = `items` row with `state='accepted'`; see `CONTEXT.md`). An asset is immutable in content after acceptance; its only possible state changes are `accepted → superseded`.

### 1.2 Deduplication precedence (matches `admission-policy.md` §2.4)

Evaluated in order for every candidate; first match wins:

| Precedence | Condition | Action |
|---|---|---|
| 0 | run_id already persisted (replay) | **Store idempotency** (ticket 07): no admission decisions, nothing changes |
| 1 | same `item_id` already decided in this run, **or** already persisted from an earlier run | **Reject `DUPLICATE_ID`**; `duplicate_of` = the existing candidate/asset id |
| 2 | normalized `url` already an **accepted asset**, or already decided (any outcome) in this run | **Reject `DUPLICATE_URL`**; `duplicate_of` = the earlier candidate/asset id. Normalization: strip `http(s)://`, trailing `/`, lowercase host (per policy §2.4) |
| 3 | same `story_fp`, different URL | **No dedup at admission.** Same-story-different-URL is evidence, not noise; Horizon's `topic_dedup=true` covers within-run story collapse, and retrieval may join via the reserved `edges(kind='same_story')` table. The legacy lossy fingerprint drop is not inherited (resolves design.md K4) |
| — | no match | Fresh admission decision per policy |

`story_fp = normalize(title) + "|" + domain(url)` (lowercase, punctuation stripped, whitespace collapsed); the algorithm's single owner is `kb/model.py`.

### 1.3 Uniqueness model

URL uniqueness is enforced **only among accepted assets** with a SQLite partial unique index (§6), so a `DUPLICATE_URL` loser can coexist in the ledger without any `items` row, and a superseded asset never blocks its successor's URL. Ledger foreign keys are explicit: `admissions.run_id → runs.run_id`; `admissions.duplicate_of` is a **candidate-identity pointer** (validated by the writer at insert time, deliberately *not* a DB FK, because the referenced candidate may exist only in the ledger); `admissions.item_id` has **no FK** (candidates are not assets); `items.first_run_id → runs.run_id`; `items.superseded_by → items.id`, declared `DEFERRABLE INITIALLY DEFERRED` because **supersede is one transaction** (ticket 07): within a single transaction the store flips the old asset to `superseded` (freeing its URL under the partial index) and inserts the accepted successor — either both commit or neither does, and the ledger gains the matching `supersede` row.

---

## 2. Candidate lifecycle and item states (criterion 2)

The four canonical states describe the **candidate lifecycle**; their storage mapping differs:

| State | Meaning | Where it lives |
|---|---|---|
| `accepted` | decision accepted; candidate became/persists as an asset | ledger outcome `accepted` + `items` row `state='accepted'` |
| `rejected` | policy, dedup, or integrity rejection — terminal for that candidate occurrence | ledger outcome `rejected`; **no** items row |
| `failed` | pre-decision failure (mapping, transport, truncation); operational, non-terminal | ledger outcome `failed`; **no** items row |
| `superseded` | asset replaced by an accepted successor that owns its story | ledger outcome `supersede` + `items` row `state='superseded'` |

```text
candidate (per run) ── decision ──► accepted  → asset row (state accepted)
        │                │         rejected  → ledger only (terminal for this occurrence)
        │                │         failed    → ledger only (retryable: next run re-fetches)
accepted asset ── supersede decision ──► superseded (terminal; superseded_by = successor id)
```

**Re-evaluation semantics** (no version-string comparisons anywhere; every candidate is decided by the *current* policy of its run; the ledger retains every decision for audit):

- **Re-fetch of an accepted asset** (same Horizon id, later run): new candidate occurrence, rejected `DUPLICATE_ID` (precedence 1). The asset is **not** re-decided, not modified, and not "re-rejected": candidate rejection ≠ asset rejection. An accepted asset's state changes only via a `supersede` decision. (An accepted item is never later rejected in P0.)
- **Rejected candidate re-admission**: a candidate rejected in run N (policy, or URL blocked) may be accepted in run N+1 simply because the current run's decision says so and the blocking condition no longer holds (URL winner superseded, policy constants changed — recorded via the new decision's `policy_version`, never compared with `>`). Nothing is permanently barred except `superseded` assets and candidates whose blocking condition still holds.
- **Failed candidate retry**: not persisted ⇒ id and URL are unblocked ⇒ the next run decides it fresh; recovery requires no refetch (Horizon stage artifacts are the source, ticket 10).
- **Idempotent replay**: replaying the same `run_id` mutates nothing (precedence 0).

Transient per-stage states (fetched/mapped/scored/…) live in the run's Horizon artifacts, not in the durable store.

---

## 3. Admission and audit records (criterion 3)

### 3.1 Ledger

`admissions` is an **append-only candidate decision ledger** — the durable replacement for `_skipped.jsonl`, keyed by the same identity string as assets:

- `PRIMARY KEY (run_id, item_id)` — exactly one decision per candidate occurrence (replays are no-ops, precedence 0; resume-safe per ticket 10).
- Every row carries `policy_id` + `policy_version` (e.g. `admission-policy@0.1.0`) and an **ordered `reason_codes` JSON array** in exactly the shared representation defined in §3.2. Accept rows are recorded too: "why is this in the library" must be as answerable as "why not".
- `evidence_json` follows the policy §3 shape (bounded, re-derivable); it is never free-form model output.
- `duplicate_of` points at the winning candidate/asset id for `DUPLICATE_*` rows; the asset-level `superseded_by` pointer lives on `items`.

### 3.2 Reason codes: one shared representation, one owner

**Representation** (agreed with `admission-policy.md` §2–§3, binding for tickets 07/09): `reason_codes` is a **JSON array of short codes in policy evaluation order** (e.g. `["ACCEPTED","TOPIC_P0_BOOST"]`), stored as TEXT. No SQL `CHECK` on contents — membership and ordering are enforced in code.

**Owner**: the registry is a single ordered data structure in **`kb/model.py`** (pure, no I/O). `admission-policy.md` §2 owns the *semantics* of policy codes; `kb/model.py` owns the *registry* (membership + namespaces). Admission modules and consumers import codes; they never declare literals (closes O2; makes G7-class drift impossible). Registered namespaces:

| Namespace | Codes (P0) | Source of semantics |
|---|---|---|
| Policy decision | `ACCEPTED`, `TOPIC_P0_BOOST`, `RESCUED_BY_TOPIC`, `REJECTED_LOW_SCORE`, `LOW_SOURCE_TYPE` | `admission-policy.md` §2.2 |
| Policy negative patterns | `NEG_HYPE_NO_MECHANISM`, `NEG_HIRING_CONFERENCE`, `NEG_SHALLOW_LAUNCH`, `NEG_GENERIC_ENTERPRISE` | `admission-policy.md` §2.3 (O3: executed in code, not prompt-only) |
| Dedup | `DUPLICATE_ID`, `DUPLICATE_URL` | `admission-policy.md` §2.4 + §1.2 here |
| Integrity (pre-decision) | `MISSING_SCORE`, `MISSING_SUMMARY`, `MALFORMED_ENRICHMENT`, `MALFORMED_METADATA`, `MISSING_PUBLISHED_AT` | `admission-policy.md` §2.5 |
| Policy (non-terminal warning) | `LOW_CONFIDENCE_MATCH` | `admission-policy.md` §2.6 |
| Transport/mapping (`failed` outcome) | `MAP_FAILED`, `TRUNCATED_STAGE`, `ENVELOPE_INVALID`, `STAGE_TIMEOUT` | ticket 01 contract research (adapter-owned failures) |
| Run-level | `ENRICHMENT_UNAVAILABLE` | `admission-policy.md` §2.5 (run row, ticket 10) |

Extending the registry is a one-place edit in `kb/model.py` (+ test fixture); the `failed` outcome uses exactly the transport/mapping namespace.

### 3.3 Run accounting and invariants

`runs` audits admission-level truth (Horizon's stage telemetry stays in its run artifacts): status derived per ticket 01's contract note, counts `fetched / mapped / accepted / rejected / failed / persisted`, and `invariant_ok`.

**Count definitions**: `fetched` = candidate occurrences returned by the radar for this run. `mapped` = candidates that produced typed store input. `failed` = candidates that failed before a decision was possible (mapping/transport; ledger outcome `failed`). `accepted` / `rejected` = ledger outcomes. `persisted` = asset rows written by this run.

**Invariants checked before a run commits** (any violated ⇒ run status `failure`, nothing persisted):

- **I1 Identity invariance** — an identity string never changes across stages or runs.
- **I2 Run closure** — `fetched = accepted + rejected + failed` and `mapped = accepted + rejected` (every mapped candidate reaches a decision; `failed` covers exactly the pre-decision failures); `persisted = accepted`; every candidate has exactly one ledger row.
- **I3 Ledger completeness** — every ledger `accepted` row has a matching `items` row; every `items` row traces to an `accept`-ing ledger row in its creation run; an asset's state is `superseded` iff a `supersede` row references it; every non-accept row carries a policy version and ≥1 reason code; `rejected`/`failed` rows never create `items` rows.
- **I4 Read alignment** — `reader` and export default to `state='accepted'`; rejected/failed candidates are visible only through explicit audit paths over the ledger.
- **I5 Idempotent replay** — replaying the same `run_id` appends nothing and mutates nothing (precedence 0); ingesting new runs over the same stories appends only honest new decisions and changes no existing asset row.

### 3.4 G1 / G2 closure

| Finding | Resolution in this model | Verified by |
|---|---|---|
| G1 (validator forbids colons; 65% of corpus has colons) | one ID definition, opaque, colon-legal; contradictory validator retired, not migrated | ticket 16 removal check; ticket 10 regression: one ID traced accepted → rejected → retrieved |
| G2 (collector ID ≠ organizer ID; `_skipped.jsonl` untraceable) | single minting point (mapper); audit ledger keyed by the canonical ID | ticket 10 invariant tests I1–I3 |

---

## 4. Single owners of enums and validation rules (criterion 4, closes O2)

| Artifact | Single owner | Rule |
|---|---|---|
| Reason-code registry, outcome/state enums, `story_fp` + URL-normalization algorithms, ID namespacing format | **`kb/model.py`** — pure, no I/O | only module allowed to declare vocabulary literals; `admission-policy.md` §2 owns policy-code *semantics*, the registry owns membership |
| Persistence constraints (DDL `CHECK`s, partial unique indexes) | **`kb/store/schema.py`** | `CHECK` lists are **generated** from `kb/model.py` enums at migration time — never copied |
| ID minting + `ContentItem` → store translation | **`kb/horizon/mapper.py`** | only module that sees radar shapes |
| Admission policy content (thresholds, detectors, evidence shape) | `kb/admission/` per ticket 03/09 | consumes the `kb/model.py` registry; returns decision records in §3.2 representation |
| Retrieval/export surface | **`kb/store/reader.py`** + `kb/store/export.py` | consumers (MCP, UI, digest) never re-declare vocab (G7-class drift becomes impossible) |

Legacy duplicated vocabularies (`analyzer.py`, `organizer.py`, `hooks/validate_json.py`, `hooks/check_quality.py`, `relevance_profile.py`) are not re-pointed; they died with the legacy path (ticket 16). Until then, the new write path never imports them. `relevance_profile.py` constants return in P1 only as imports of `kb/model.py`.

---

## 5. Field provenance (criterion 5)

Assets are **write-once at acceptance** (§1.1): copied fields are transcribed once and never refreshed — a re-fetched candidate is rejected `DUPLICATE_ID`, so there is no later-wins update path; the only mutable columns are `state`, `superseded_by`, `updated_at` (via supersede only).

| Class | Fields | Rule |
|---|---|---|
| **Authoritative** (owned here, never recomputed from upstream) | `id`, `state`, `superseded_by`, `first_seen_at`, `first_run_id` | set once; `state` changes only via supersede decisions |
| **Copied** (transcribed verbatim from the radar at acceptance) | `source_type`, `title`, `url`, `author`, `published_at`, `fetched_at`, `metadata_json`, `profile`, `profile_method`, `profile_confidence`, `profile_reason`, `score`, `score_reason`, `summary`, artifact titles/blocks/sources/source-refs | write-once; unknown upstream fields survive only inside `metadata_json` (bounded) |
| **Derived** (computed here from copied data, pure functions) | `content_main`/`content_comments` (COMMENTS_MARKER split), artifact block `position` (list order — upstream has no position field), `story_fp` (normalized URL may supersede the raw `url` for dedup), `tags` rows, `updated_at`, FTS index | computed at acceptance; single owner per algorithm |
| **Discarded** (intentionally not persisted) | legacy personalization: `personal_fit_score`, `learning_track`, `learning_tags`, `relevance_reason`, `priority_score`, `reading_priority`, `suggested_action`, `confidence`, legacy 1–10 `score` mirror (D7: concept retained, reimplemented in P1); Horizon internals: `data/mcp-runs` paths, artifact file paths, run-store filenames, raw MCP envelopes/meta, Rich output | must have **no column**; presence in any new write path is a review failure |

---

## 6. Reference DDL (delta over design.md §2)

Supersedes the `items` and `runs` tables in design.md §2; adds `admissions`. Enum lists shown inline are generated from `kb/model.py` at migration time. `reason_codes` is JSON validated in code (§3.2), intentionally without a SQL CHECK. `PRAGMA foreign_keys = ON` (design.md §2) is mandatory: the FKs below are part of the model, not decoration.

```sql
CREATE TABLE IF NOT EXISTS items (            -- accepted assets only (candidate vs asset, §1.1)
  id                 TEXT PRIMARY KEY,        -- candidate id of the accepting decision
  state              TEXT NOT NULL CHECK (state IN ('accepted','superseded')),
  superseded_by      TEXT REFERENCES items(id) DEFERRABLE INITIALLY DEFERRED,  -- supersede is one transaction (§1.3)
  source_type        TEXT NOT NULL,
  title              TEXT NOT NULL,
  url                TEXT NOT NULL,
  author             TEXT,
  published_at       TEXT,
  fetched_at         TEXT NOT NULL,
  story_fp           TEXT,
  profile            TEXT,
  profile_method     TEXT,
  profile_confidence REAL,
  profile_reason     TEXT,
  score              REAL,
  score_reason       TEXT,
  summary            TEXT,
  content_main       TEXT,
  content_comments   TEXT,
  metadata_json      TEXT,
  first_seen_at      TEXT NOT NULL,
  first_run_id       TEXT NOT NULL REFERENCES runs(run_id),
  updated_at         TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_url   ON items(url) WHERE state = 'accepted';
CREATE INDEX IF NOT EXISTS idx_items_story ON items(story_fp);
CREATE INDEX IF NOT EXISTS idx_items_state ON items(state);

CREATE TABLE IF NOT EXISTS admissions (       -- append-only candidate decision ledger (§3.1)
  run_id         TEXT NOT NULL REFERENCES runs(run_id),
  item_id        TEXT NOT NULL,               -- candidate identity; no FK: candidates need not be assets
  outcome        TEXT NOT NULL CHECK (outcome IN ('accepted','rejected','failed','supersede')),
  policy_id      TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  reason_codes   TEXT NOT NULL,               -- JSON array, ordered, kb/model.py registry (§3.2)
  evidence_json  TEXT,                        -- admission-policy.md §3 shape
  duplicate_of   TEXT,                        -- candidate-identity pointer; writer-validated, no DB FK (§1.3)
  decided_at     TEXT NOT NULL,
  PRIMARY KEY (run_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_admissions_item ON admissions(item_id);

CREATE TABLE IF NOT EXISTS runs (
  run_id       TEXT PRIMARY KEY,
  radar        TEXT NOT NULL,
  radar_ref    TEXT NOT NULL,
  config_hash  TEXT,
  started_at   TEXT NOT NULL,
  finished_at  TEXT,
  status       TEXT NOT NULL CHECK (status IN ('success','partial_failure','failure')),
  fetched      INTEGER NOT NULL DEFAULT 0,
  mapped       INTEGER NOT NULL DEFAULT 0,
  accepted     INTEGER NOT NULL DEFAULT 0,
  rejected     INTEGER NOT NULL DEFAULT 0,
  failed       INTEGER NOT NULL DEFAULT 0,
  persisted    INTEGER NOT NULL DEFAULT 0,
  invariant_ok INTEGER NOT NULL DEFAULT 1,
  sources_json TEXT
);
```

`tags` / `artifacts` / `artifact_blocks` / `artifact_sources` / `block_source_refs` / `edges` / FTS: unchanged from design.md §2. Application code treats `admissions` as append-only (insert-only API in `kb/store/writer.py`).

---

## 7. Deliberately not decided here

- Policy content: thresholds, negative-pattern matching, evidence shape → ticket 03 (design, now **Accepted**) / ticket 09 (implementation). This model fixes only the record shape and the shared reason-code representation/registry.
- Run mechanics: composition, resume, interruption → ticket 10, bound by §3.3 invariants.
- Schema implementation details (migration versioning, FTS fallback) → ticket 07, bound by §6.
