---
name: llm-wiki-lint
description: "Stage 2 audit of the knowledge pipeline in docs/knowledge-model.md: a read-only health check over a knowledge instance — the L1–L4 coverage matrix (all four sections present, each filled or an explicit gap), the two-way sources: audit (every footnote id appears in sources:, every entry is used), footnote resolution, ext: verification, narrative.md ↔ pages consistency, index.md completeness, concept-map MECE, broken links, orphans, frontmatter, tag sprawl, language, confidence, materials.md sha256 drift against the external read-only archive, and used-in grammar. Never writes — it reports findings and prints the log.md line for you to append; no gate. Use when the user says 'lint', 'audit', 'health-check', 'review the wiki', 'check for broken links', 'check provenance', or asks whether a wiki is complete and traceable."
---

Last updated: 2026-10-09

# LLM Wiki — Lint

The audit stage of the pipeline in [docs/knowledge-model.md](../../../docs/knowledge-model.md):
a knowledge **instance** in, one report out. It reads the whole instance and re-hashes the external
archive, checks the pages against the model, and writes **nothing** — not a page, not the archive,
not `log.md`.

**Announce at start:** "I'm using the llm-wiki-lint skill to audit this instance."

**When to run:** on demand, at the end of a run, or before treating an instance as authoritative.
There is no cadence: the report includes a readout of how many `log.md` actions have happened since
the last lint, so staleness is visible rather than assumed. Lint is not a gate and holds nothing;
everything it finds is either a defect to fix in the stage that owns it or an honest coverage state.

## Invocation and inputs

| Input | Rule |
| :-- | :-- |
| `$KB_PATH` | **Required, explicit, never a default.** The instance root. |
| Archive root | Read from `materials.md`'s header line `archive: <abs-path>`. **Never** `$WIKI_PATH`, never a default, never a glob. |
| Topic | Optional. Read it from `SCHEMA.md`'s Domain section — never derive it from the folder name. |

Each expected instance file is located **only** at its canonical name under `$KB_PATH`:
`SCHEMA.md`, `narrative.md`, `sources.md`, `materials.md`, `wiki/`, `index.md`, `log.md`. There is no
fallback search and no `wiki/`-as-root guess. **A missing expected file is itself a finding**: report
it once at the severity its class earns (`narrative.md`, `sources.md` and `materials.md` are
Critical — the structural and provenance checks have no referent without them), then skip the checks
that depend on it with a note, rather than aborting the report.

## Hard Rules

1. **Read-only, zero writes.** Lint never writes a page, the archive, `log.md` or any other file. It
   prints the exact `log.md` line to append and the caller appends it. Prove it (check H3).
2. **Never "fix" a finding.** No auto-fix, no auto-merge, no auto-graduate, no frontmatter rewrite,
   no log rotation. Every finding is reported with its action for a human. Structural corrections
   rewrite prose, and prose is not lint's to write.
3. **The model is the source of every rule.** Each check cites `docs/knowledge-model.md`. If a check
   needs a rule the model does not state, say the model is silent — do not invent one.
4. **Report every finding with path + issue + suggested action.** A finding without a location is not
   actionable.
5. **The archive is read-only, absolutely.** Re-hashing is the only thing lint does to it, and
   re-hashing reads.

## What lint reads, what it audits, what it does not

**Reads:** `SCHEMA.md` (conventions), `narrative.md` (the agreed architecture), `sources.md` (the
registry), `materials.md` (`sha256`, `archive:`), `index.md`, `log.md`, `wiki/*.md`, and the external
archive **read-only** (re-hash only).

**Audits:** the page set, and the two registries' consistency with the pages — nothing else.

**Does not audit `notes/`.** The evidence layer is `clean-notes`'s output and the model defines no
lint check over it. This is a boundary, not a gap. Pages cite `mat:`/`ext:` ids, never note files, so
there is deliberately no page ↔ note link check either.

## Orientation (always first)

① `SCHEMA.md` — the instance's conventions: body language, level template, update policy.
② `narrative.md` — the agreed hierarchy, threads and core-concept list the pages are checked against.
③ `sources.md` — the provenance registry.
④ `materials.md` — the `archive:` path and the `sha256` column the drift check uses.
⑤ `index.md` — the page inventory.
⑥ last 30 lines of `log.md` — recent activity, and the last `lint` entry for the staleness readout.

## Triage (before the checklist)

Weight the report before running it, so a systemic defect is not answered with leaf-level fixes:

- **Many pages with a `gap` level, or sparse text** → the narrative promised material that does not
  exist. Recommend the ingest gate, not N page-level edits.
- **Many unresolved footnotes, or `sources.md`/`materials.md` behind the pages** → re-run the stage
  that owns the registry (`llm-wiki-ingest` 2b for `ext:`, `map-materials` for `mat:`), not the pages.
- **Pages outside the narrative, or a `narrative.md` newer than its pages** → the narrative changed
  after the pages were written; the answer is a re-ingest, not per-page surgery.
- **A whole class of findings inside one stage's output** → fix the stage, not the leaf.

Use the triage to weight the executive summary and to avoid recommending micro-fixes; then run every
check anyway.

## The checks

Every check is `[human-review]` or `[info]` — lint has no auto-fix. `[human-review]` = a defect that
needs a human decision; `[info]` = a readout, no action expected.

### Provenance

**P1 · Footnote resolution** `[human-review]`
Footnotes are `[^mat:m007]` / `[^ext:vaswani-2017]`, with matching `[^…]: …` definition lines in the
page's `## References` section. For each reference:

- a reference with no matching definition line is **unresolved**;
- a `mat:` id must be a row in `materials.md`;
- an `ext:` id must be a row in `sources.md` **with a verified payload** — `url`, `version`,
  `fetched_at`, `sha256`, `verified` all present. An `ext:` id with no verified row is not usable
  (model § Provenance, rule 2) and is **Critical**. Lint **shape-checks** the row; it never re-verifies
  the `sha256`, which records the bytes read once at registration and is not a reproducible artifact.

```bash
python3 - "$KB" <<'PY'
import re, sys, pathlib
kb = pathlib.Path(sys.argv[1])
pages = sorted((kb / "wiki").glob("*.md"))
ref = re.compile(r"\[\^([A-Za-z][\w-]*:[^\]\s]+)\]")
for p in pages:
    t = p.read_text()
    ids = set(ref.findall(t))
    defs = set(re.findall(r"^\[\^([^\]]+)\]:", t, re.M))
    print(p.name, "unresolved:", sorted(ids - defs))
PY
```

**P2 · Two-way `sources:`** `[human-review]` — the audit surface that makes provenance checkable.
Every footnote id on a page appears in that page's `sources:` list, and every entry in `sources:` is
used by at least one footnote (model § Provenance, rule 6). Report each direction separately: an id
used but missing from `sources:` and an entry listed but unused. **Critical** — this is the check that
catches a page whose provenance index has drifted from its claims.

**P3 · Provenance coverage** `[human-review]`
Every body **paragraph** carries at least one footnote (model Invariant 2, "every claim traces").
A paragraph is a non-empty prose block in an `## L1`–`## L4` body, outside any fenced code block, any
table, the frontmatter and the `## References` section. **A one-statement `gap` body is exempt** — a
gap names an absence, it makes no claim (its body may wrap over several source lines). Count
paragraphs with zero `[^…]` references.

**P4 · `sources.md` row integrity** `[human-review]`
Per row: `kind` is `primary` or `secondary`; `version` is present and pins the exact version read
(`v7`, not "the paper"); `url` and `fetched_at` present; no duplicate `id`; `verified` marked. A
missing `version` is a version-pinning violation (model § Provenance, rule 3).

### Structure and narrative

**S1 · L1–L4 coverage matrix** `[human-review]` — the report's centrepiece.
Every page has all four `## L1 · …` … `## L4 · …` headings, in order, with `## References` last; a
folded-concept `##` section (model § The concept page template) may sit between L4 and `## References`
and is **not** a level. A missing heading is a violation, never an omission. Parse `levels:` from the
frontmatter: its keys are exactly `L1, L2, L3, L4`, its values are in `full | partial | stub | gap`.
Cross-check each value
against the body: a non-`gap` level must have a non-empty body; a `gap` level's body is one explicit
statement naming what is missing; a level with an empty body is a violation regardless of the declared
value. Report the whole matrix — page × level → declared value and body state — so coverage is read
at a glance.

**S2 · `narrative.md` ↔ pages consistency** `[human-review]` — the collectively-exhaustive half of
wiki-level MECE. Both directions:

- **narrative → pages:** every concept row in `narrative.md`'s core-concept list has a page.
- **pages → narrative:** every page's `threads:` is non-empty and names threads `narrative.md`
  declares; every declared thread has at least one page; every `parent:` resolves to another page or
  to the domain root (`—`, the only non-page value, and the root page is the only page that uses it).

A core concept with no page is the flagship finding — the narrative promises depth that is not there.

**S3 · Concept-map MECE — duplicate-home candidates** `[human-review]` — the mutually-exclusive half,
best-effort by design. Flag as a **fold candidate** (never fold automatically): two pages sharing a
`title` or slug, or a page whose slug equals a `##` heading inside another page. Semantic near-overlap
("two pages explain one idea") is not machine-decidable; lint reports candidates and says so.

**S4 · Core-concept target range** `[info]`
Page count against the range `narrative.md` declares (e.g. `Core-concept target: 5–8`). Over the
range is a signal to fold, raised here, not a hard failure.

**S5 · `index.md` completeness** `[human-review]`
Every page in `wiki/` has an entry in `index.md`, and every `index.md` entry has a page. A page
present in `narrative.md` and `wiki/` but missing from `index.md` is a finding — the model pairs
every page write with an `index.md` update, and nothing else checks the index half.

### Frontmatter and tags

**F1 · Frontmatter validation** `[human-review]`
Required on every page: `title`, `parent`, `threads`, `levels`, `sources`, `created`, `updated`.
Optional: `contested`, `contradictions`, `confidence`. `tags` is **optional** — validated only if
present (must be a list). `updated` present and ≥ `created`.

**F2 · Tag sprawl audit** `[info]`
The SCHEMA tag list is **open**; sprawl is audited, not forbidden (model § `SCHEMA.md`). Report
near-duplicate tags (`attention` / `attentions`, `norm` / `normalization`) and one-off tags used on a
single page. A new tag is not a finding; a redundant spelling of an existing one is.

### Links

**L1 · Broken wikilinks** `[human-review]`
Every `[[slug]]` (or `[[slug#anchor]]`) resolves to a `wiki/<slug>.md` — or, for an anchor, to a
heading inside it. Report each target that does not resolve.

**L2 · Orphan pages** `[info]`
A page with zero inbound `[[links]]` **and** named as no page's `parent` **and** absent from
`narrative.md`'s core-concept list. A page that carries a thread is not an orphan.

**L3 · Outbound-link readout** `[info]`
Pages with fewer than two outbound `[[links]]` (SCHEMA convention). Readout only.

### Registries and materials

**M1 · `materials.md` sha256 drift (read-only, external archive)** `[human-review]`
Resolve the archive from `materials.md`'s `archive:` header; if absent or nonexistent, report
**Critical** and skip this check with a note. Then re-hash **in place, without writing**:

- **File and section rows** — a section row `file.md § Heading` hashes its file. Group rows by
  resolved path, hash each **distinct** file once with a streaming sha256 over raw bytes, compare
  against the row's `sha256`. Report old vs new hash on mismatch; `missing` when the file is absent;
  `unreadable` when it cannot be opened. A row whose `sha256` cell is absent or not 64 hex characters
  is reported here too (it cannot participate in drift detection).
- **Folder rows** (`path` ends `/**`) — recompute the **manifest digest exactly as `map-materials`
  defines it**: the sha256 of the `«file sha256»\t«archive-relative path»` lines for the row's
  **covered files** (the remainder — the prefix minus any paths that have their own exception row),
  sorted by hash then path, joined by newlines **with a trailing newline**, with the same exclusions
  (`*.tmp`, `.DS_Store`, `Thumbs.db`, `materials.md`, `.git/`, `__pycache__/`, `.ipynb_checkpoints/`).

Every row is verified regardless of `kind`/`role` — an `off-topic`, `peripheral` or `redundant-of` row
is still a row a later stage may read. A mismatch means the archive changed after the map was written;
it is a finding about the world, not a fault to fix in the archive.

```bash
python3 - "$KB" <<'PY'
import hashlib, re, sys, pathlib
kb = pathlib.Path(sys.argv[1])
hdr = re.search(r"^archive:\s*(.+)$", (kb / "materials.md").read_text(), re.M)
root = pathlib.Path(hdr.group(1).strip()).expanduser() if hdr else None

def fhash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# Parse the table: id, path, sha256. Hash each distinct file once; compare.
# For a `file.md § Heading` row hash file.md; for a `dir/**` row, digest the
# sorted "<hex>\t<relpath>" lines of the subtree (same recipe as map-materials).
PY
```

**M2 · `used-in` grammar** `[info]`
Each `used-in` cell parses as comma-separated `<subject> § <section>` tokens, or `planned, unused`, or
`—`. Lint checks the grammar only — the column is `archive-materials`'s (Writing Assistant), and
whether a subject is real is not lint's call. The other half of the interface — that no non-`used-in`
cell changes across a `map-materials` re-run — needs two runs to compare and is out of scope here.

### Content health

**C1 · Contested pages** `[human-review]`
Pages with `contested: true` or a non-empty `contradictions:` list. These require human resolution
before claims harden (model § `SCHEMA.md`, update policy).

**C2 · Confidence readout** `[info]`
Pages with `confidence: low`.

**C3 · Page size** `[info]`
Pages over 200 lines — a split candidate, advisory only.

**C4 · Should-graduate** `[info]`
A `##` section whose body has outgrown its host (roughly 60+ lines, or 2+ of the page's `sources:`
aimed at it). The mirror of folding: report parent + section + signals; never auto-split.

**C5 · Language consistency** `[human-review]`
Body prose in `SCHEMA.md`'s declared language. Flag genuine drift into another language, **not** bare
canonical terms or book titles — a repeated term like `财商` in otherwise-English prose is not drift.
Report path + snippet + "rewrite to {body_language}"; never auto-rewrite. Reuse the same two-signal
heuristic: CJK sentence punctuation in a CJK-title-stripped body, or a prose line >30% CJK.

### Housekeeping

**H1 · Log rotation readout** `[info]`
Entries in `log.md` against the threshold (`SCHEMA.md` if it states one, else 500). Report
"rotation needed: yes/no". Never rotate — that is a write.

**H2 · Lint staleness readout** `[info]`
Count `log.md` entries since the last `## […] lint |` entry; report "lint last ran: <date> / never"
and the action count since. No counter state, no threshold — just visibility.

**H3 · Read-only proof** `[info]`
Touch a session marker **outside both trees** before reading, then assert nothing changed:

```bash
MARK=$(mktemp -t lint-session.XXXXXX)
# ... run every check ...
find "$KB" "$ARCHIVE" -type f -newer "$MARK" \
  ! -name '.DS_Store' ! -name 'Thumbs.db'
rm -f "$MARK"
```

Expect no output. Lint's reads cannot change an mtime, so any output means something wrote during the
audit — possibly a concurrent writer, so report it rather than treating it as proof of lint
misbehaviour.

## Report format

Group findings by severity; one line per finding with path + issue + suggested action. The coverage
matrix (S1) is reported in full. Then the executive summary, weighted by the triage.

```
## Lint Report — YYYY-MM-DD | $KB_PATH

### Critical
- Unresolved footnotes: N (page: target)
- ext: id without a verified row: N (page: id)
- Two-way sources: N (unused entries / missing ids)
- Missing instance file: narrative.md / sources.md / materials.md

### High
- Coverage-matrix violations: N (page: level)
- narrative.md ↔ pages: N (concept without page / page outside narrative / parent unresolved)
- Broken wikilinks: N
- Provenance-coverage gaps: N (page: paragraph)
- Archive drift: N (row: old → new) / missing: N / unreadable: N

### Medium
- Frontmatter: N (page: field)
- sources.md row integrity: N (id: issue)
- Contested pages: N
- Language drift: N (page: snippet)
- Fold candidates (MECE): N (pages/cluster)
- used-in grammar: N

### Low
- Orphans: N
- Page size >200 lines: N
- Should-graduate sections: N
- confidence: low pages: N
- Tag sprawl: N (near-duplicate / one-off)

### Info
- Core-concept target range: N pages vs <range>
- Log rotation needed: yes/no
- Lint last ran: <date> / never (N actions ago)
- Read-only proof: empty ✓ / N files newer
- Outbound-link readout: N

### Coverage matrix (S1)
| page | L1 | L2 | L3 | L4 |
| :-- | :-- | :-- | :-- | :-- |
| attention | full | full | partial | gap |
```

And print the log line for the caller to append (lint does **not** append it):

```
## [YYYY-MM-DD] lint | N issues found (X critical, Y high, Z medium)
```

## Contract test

Given a fixture instance and a fixture archive containing byte-changed files:

- every page's four `## L1`–`## L4` headings are checked, and a page missing one is reported, with
  `levels:` cross-checked against each body (a declared `full` with an empty body is a violation; a
  declared `gap` with a one-statement body is not);
- a footnote present on a page but absent from `sources:` is caught, and a `sources:` entry used by no
  footnote is caught (both directions of P2);
- an `ext:` id with no `sources.md` row, or a row without `url`/`version`/`fetched_at`/`sha256`, is
  caught;
- a core concept listed in `narrative.md` with no page is caught; a page whose `threads:` names an
  undeclared thread is caught;
- a file whose bytes changed after mapping is caught with old vs new hash; a folder row's digest is
  recomputed with the same recipe `map-materials` uses; a missing file is reported `missing`;
- a paragraph with no footnote is counted (a `gap` level's one-statement body is not);
- a page present in `wiki/` but absent from `index.md` (or vice versa) is caught (S5);
- a missing `narrative.md` is reported once and its dependent checks are skipped with a note, not
  crashed;
- running lint leaves `git status` for the instance and the archive byte-identical, and the
  read-only proof returns empty;
- the log line was **printed**, not appended.

## Handoffs

**In:** `$KB_PATH` (required, explicit). Everything else is read from the instance.

**Out:** a report, and the exact `log.md` line for the caller to append. Nothing is written.

**Boundaries:**
- vs `map-materials`: that writes `materials.md`; lint checks its `sha256` column for drift and its
  `used-in` grammar, and never edits a cell.
- vs `clean-notes`: that writes `notes/`; lint does not audit the evidence layer.
- vs `llm-wiki-ingest`: that bootstraps `SCHEMA.md` and writes the pages; lint checks the pages
  against `narrative.md`, `sources.md` and the model, and writes nothing.
