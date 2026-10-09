# Knowledge model

Last updated: 2026-10-09

Status: frozen 2026-10-08 (wayfinder ticket **Lock the knowledge model**). The four KB skills — `map-materials`, `clean-notes`, `llm-wiki-ingest`, `llm-wiki-lint` — cite this file as their single source. Change it here first, then in the skills.

## Locating this contract

The canonical owner is `XinheLIU/Agentic-Knowledge-Bank`, path `docs/knowledge-model.md`;
the glossary is **root-level** `CONTEXT.md`. A deployed skill uses an explicit
`KB_MODEL_ROOT` checkout, or reads these paths from the canonical repository at its installed
source revision. Record the resolved location and revision (or working-tree hash). Do not resolve
repository-relative links from a flattened installation, vendor a model copy into each skill, or
silently substitute another product's conventions. If the contract cannot be read, report the
missing dependency before writing instance content.

## Purpose

Agentic-Knowledge-Bank builds **provenance-tracked concept wikis**. A knowledge instance is the durable output: a topic's understanding, structured by narrative, deep enough inside each concept to be studied from, and traceable paragraph by paragraph to the raw material or the primary source a claim came from.

The product's two goals:

1. **Cognitive asset accumulation** — a wiki derived from raw notes where every claim is traceable to a raw note or to an authoritative primary source.
2. **Cognitive compounding** — deferred. Not designed here.

## Vocabulary

Canonical terms are frozen in [CONTEXT.md](../CONTEXT.md). The load-bearing ones:

| Term | Meaning |
|---|---|
| **archive** | The external, read-only folder of accumulated raw material (the source of truth you did not write). Never a stage. |
| **instance** | One topic's knowledge base — a folder holding `SCHEMA.md`, `narrative.md`, `sources.md`, `materials.md`, `notes/`, `wiki/`, `index.md`, `log.md`. |
| **material** | One file, or one `##` section of one file, in the archive. |
| **note** | A stage-1 evidence document: a topic's material merged, deduplicated and clustered. |
| **concept page** | A stage-2 wiki page: one core concept at four depth levels, with per-paragraph provenance. |
| **thread** | A named sequence of concepts that carries part of the narrative. The unit that makes a concept page-worthy. |
| **provenance id** | `mat:m007` (a `materials.md` row) or `ext:vaswani-2017` (a `sources.md` row). |

## The three stages

```
archive/  ──map-materials──▶  materials.md  ──clean-notes──▶  notes/  ──llm-wiki-ingest──▶  wiki/
 (read-only)   stage 0: inventory    (evidence)   stage 1: structure  (evidence)  stage 2: narrative  (presentation)
```

The stages have different jobs on purpose. `materials.md` inventories. `notes/` **is evidence** — what the material says, deduplicated and grouped, with nothing added and nothing improved. `wiki/` **is presentation** — a concept explained to four depths, in an order a reader follows. Collapsing any two of them loses either traceability or readability.

**Evidence grouping is block-level.** Each retained claim block has one topic home; a material row
may feed several notes. Split mixed-topic lists into coherent claim blocks without separating a
claim from its qualifications or provenance. Merge repeated claims into the fuller block; retain
distinct angles. Each merge names the actual destination section/block and the unique claims it
absorbed, not merely a same-topic introduction.

**Stage-1 supplementation is provisional.** For a fact without which a note is unreadable,
`clean-notes` may include a visibly marked supplement and a `## Supplementation (ext:)` block
with candidate id, fact, URL, version, fetch date and hash. It never writes `sources.md`.
These are handoff candidates, not registered page citations. Ingest 2b verifies the exact claim
and version before registration, or reuses an already verified row for that work/version; it
never edits the note. Unverifiable candidates are omitted from pages and the missing coverage is
reported. A conflicting id gets a new page-side id and an explicit mapping in the ingest log.

**Gates respect caller authorization.** Normally await the author's decision. When the caller
explicitly delegates unattended decisions, record question, options, choice and reason in the
stage's report (and ingest's existing log); this adds no new artifact writer or permission.

### Instance layout

The **archive is not inside the instance**. It is an external folder, referenced by absolute path, and never written to. `materials.md` lives in the instance, not the archive.

```
<domain>-kb/                     the instance
├── SCHEMA.md                    conventions: domain, language, tags, level template, update policy
├── narrative.md                 the agreed architecture: hierarchy tree, threads, core-concept list
├── sources.md                   provenance registry: verified primary/secondary sources
├── materials.md                 stage 0: the archive inventory, one row per material
├── notes/<topic>.md             stage 1: MECE evidence notes
├── wiki/<slug>.md               stage 2: concept pages
├── index.md                     one entry per page
└── log.md                       append-only action log
```

Example: archive `/Users/…/Transformer/Transformer-materials`, instance `/Users/…/Transformer/Transformer-kb`.

**Location.** The instance root is an explicit parameter (`$KB_PATH`), never a default. The archive path is recorded in `materials.md`'s header as an `archive: <abs-path>` line — the instance knows its own archive, so no skill hard-codes a path and no `$WIKI_PATH`-style env default exists.

**The archive is read-only, absolutely.** No skill writes into it — not a map, not a rename, not a hash refresh, not a `.DS_Store` sweep. `map-materials` proves it by asserting no file in the archive is newer than the session start.

**Read-only proof is distinct from inventory.** Before/after manifests cover every file, including
junk, with relative path, byte hash and nanosecond mtime; also check a session-start marker.
Temporary proof files live outside protected trees and are removed afterwards. All stages may
read/hash for this proof; only map-materials updates inventory hashes. Lint extends the proof to
the whole instance. Git status alone is insufficient, and no git repository is required.

> Decision record: [ADR 0002 — The archive is external and read-only; the wiki is a derived view](adr/0002-external-read-only-archive.md).

## Hierarchy

Three levels, top-down: **domain → thread → core concept**.

- The **domain** is the instance (`transformer`).
- A **thread** is a named line of the narrative (`attention-lineage`, `normalization`), recorded in `narrative.md`.
- A **core concept** is a page (`attention`, `multi-head-attention`).

Every page declares its position in the hierarchy:

```yaml
parent: transformer          # the page it hangs under
threads: [attention-lineage] # the thread(s) it belongs to
```

**Sub-variants are `##` sections inside the parent page, not pages.** A variant becomes its own page only at the gate.

## The concept page template

Every page has these body sections, **in this order, always** — a missing section is a `gap`, never an omission:

```markdown
---
title: Attention
parent: transformer
threads: [attention-lineage]
levels: {L1: full, L2: full, L3: partial, L4: gap}
sources: [mat:m007, mat:m012, ext:bahdanau-2014, ext:vaswani-2017]
created: 2026-10-08
updated: 2026-10-08
contested: true              # optional
contradictions: [self-attention]  # optional
confidence: high             # optional
---
## L1 · What it is
problem solved, origin (who/when), use cases, core sub-concepts, diagram
## L2 · Relations
[[links]] with a relation type (generalizes / variant-of / prerequisite / contrasts) + core questions
## L3 · Math & code
derivation, shapes, reference implementation
## L4 · Extensions
adjacent topics, further reading, open questions
## References
footnotes → sources.md / materials.md
```

**The root page.** The page at the top of a hierarchy carries `parent: —`. `—` is the **domain root** and is the only `parent:` value that is not a page slug. `narrative.md` declares it once as `root page: <slug>`, and the domain label carries a suffix (`transformer (domain)`) so it never collides with the same-named root page. Every other `parent:` names a page slug.

**A folded concept.** A concept that folds into a page (see **Page admission**) gets its own `##` section after the four level sections and before `## References`. `levels:` describes the four level sections only; a folded section is detailed sub-concept content, not a fifth level.

### The four levels

| Level | Answers | Sourced from |
|---|---|---|
| **L1 · What it is** | What problem, what origin, what is it made of | notes (and primary sources) |
| **L2 · Relations** | How it connects to what else, and what to ask next | notes + narrative |
| **L3 · Math & code** | The derivation, the shapes, a reference implementation | notes, supplemented from primary sources |
| **L4 · Extensions** | What's adjacent, what's open | primary sources, explicitly marked as beyond the raw |

### Coverage status

`levels:` records **coverage**, not content. Four values:

| Value | Meaning |
|---|---|
| `full` | The level answers its question from real material |
| `partial` | Answers it in part; the page says what is missing |
| `stub` | A pointer to where it belongs, or a single sentence |
| `gap` | No material and no verified source exists |

A `gap` body is **one explicit statement** — a single block, possibly wrapped over several source lines — naming what is missing. It is never silently empty, and it is never filled by invention. `partial` and `stub` are honest self-assessments, not failures — the coverage matrix is the point.

`full` requires the listed template content, not merely a non-empty body. In particular L1 includes
a sourced diagram (an inherited image or a diagram of sourced relationships). If a required item
is unavailable, declare `partial`, name it, and revisit admission at the gate. Lint separates its
executed presence checks from semantic review; it never certifies pedagogical completeness from
heading presence alone.

## Assets and audit scope

Local image and asset destinations in `notes/` and `wiki/` must be valid CommonMark/GFM:
percent-encode spaces and reserved path characters (for example `image%20name.png`), or use
an angle-bracket destination (`![alt](</absolute/image name.png>)`). Never emit a bare raw-space
destination. Decode the URL path once when resolving the file; resolve relative paths against the
containing Markdown file. Stage 1 emits absolute archive paths and preserves external URLs.
Stage 2 preserves the valid destination and the image's provenance. Archive relocation requires
stage-owned link repair as well as updating the inventory header; changing the header alone does
not repair absolute links.

An image must render as an `<img>` with non-empty alt text; its decoded local `src` must name an
existing, non-zero image with recognized image magic bytes (or valid SVG markup). Existence or a
`.png` suffix alone is insufficient. Audit intended image syntax as well as successfully parsed
images, so malformed raw-space destinations cannot disappear from the denominator. Other local
asset links must render as links and resolve to existing non-zero files. Lint reports failures and
unsupported formats without fetching or rewriting. External URLs remain external: rendering/alt
can be checked offline, but remote bytes are reported **not verified**, never a local-file pass.

Lint audits page structure/provenance plus image and asset links in **both notes and pages**.
It does not certify notes' semantic deduplication or fidelity. Claim provenance covers folded
sections as well as L1–L4; lists, tables and diagrams need citations on the claim or its introducing
paragraph. References, frontmatter, code syntax and explicit absence statements are not claims.
The core-concept slug set in `narrative.md` must equal the page slug set in both directions.

Size, orphan, tag-sprawl, language-detection and staleness formulas in lint are **advisory
heuristics**, not model invariants. A source count alone never establishes that a fold has outgrown
its host. Confirm language drift by reading the prose. No heuristic authorizes a split or rewrite.

## Provenance

**Every paragraph carries at least one provenance id.** A footnote:

- `mat:m007` — points at a row in `materials.md`
- `ext:vaswani-2017` — points at a row in `sources.md`

**Two sources, two jobs.** An id prefix names the artifact it points at, not a stage: `mat:` is the archive inventory, `ext:` is a fetched primary source. (There is no `raw:` prefix — `raw` names the *stage*, and the plan's external folder is the **archive**.)

### The rules

1. **Per-paragraph, not per-page.** Provenance is a property of a claim.
2. **`ext:` ids must be verified.** A row in `sources.md` with a real URL, a `fetched_at` date, and a `sha256` of the body actually read. An `ext:` id with no verified row is not usable. Verification happens **once, at registration**: a live page is not byte-stable, so the `sha256` records the bytes read at that moment and is never re-verified; lint only shape-checks the row.
3. **Version pinning is mandatory.** Where a work has multiple versions (`1706.03762` has seven), the id records the exact version read — `ext:vaswani-2017` resolves to a `version: v7` row. "The paper" is ambiguous and insufficient.
4. **Supplemented content is marked.** Content that came from a primary source rather than the notes is visibly distinct from note-derived content.
5. **No verified source → `gap`, not invention.** If a level needs a source that cannot be verified, mark `levels: Lx: gap` and say so. Inventing content is the one unrecoverable failure.
6. **`sources:` is the page's provenance index.** Every footnote id on the page appears in `sources:`, and every entry in `sources:` is used by at least one footnote. This is a two-way check lint enforces — it is an audit surface, not a duplicate.

### `sources.md` — the provenance registry

Instance-scoped. Records what a claim is traceable to.

```markdown
# Sources — transformer

Last updated: YYYY-MM-DD

| id | kind | title | url | version | fetched_at | sha256 | verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| vaswani-2017 | primary | Attention Is All You Need | https://arxiv.org/abs/1706.03762 | v7 | 2026-10-08 | <hex> | ✅ |
| d2l-11.7 | secondary | Dive into Deep Learning §11.7 | https://d2l.ai/… | 1.0.3 | 2026-10-08 | <hex> | ✅ |
```

`kind` is `primary` or `secondary`. **Not `tier`** — trust rating is a different axis (below).

- **primary** — the work itself: paper, official docs, canonical repo.
- **secondary** — an exposition of the work: textbook, course notes. Usable as an `ext:` anchor for *explaining*, never for a priority claim ("first introduced", "proves").

`materials.md`'s `source-id` column — added later as a late column by its owner (above) — is the join key into the cross-topic registry (`sources/<domain>.md`, owned by Information Assistant): instance provenance and cross-topic trust are **two axes, two files**, linked by id. They are not merged.

> Decision record: [ADR 0003 — Instance provenance and cross-topic trust stay separate files](adr/0003-provenance-and-trust-separate-files.md).

## Page admission

A concept earns a page only if it satisfies **both**:

1. **It carries a thread** in `narrative.md`, and
2. **It can fill L1 fully and L2 meaningfully** from available material.

Otherwise it **folds into the page that owns it**, as a `##` section. When uncertain, fold: under-splitting is cheap to fix later, over-splitting scatters one idea across thin stubs.

This replaces "one page = one atomic concept". That rule produced **119 pages** for one topic including `rope`, `moe-router` and `fully-connected-layer` as peers of `attention`. The failure was granularity, not page type — the model already was per-concept. The fix is the floor, not a new page model.

**The instance declares a core-concept target range** in `narrative.md` (Transformer: 5–8). Exceeding it is a signal to fold, and is raised at the gate — not a hard cap, but a checked assumption.

## `narrative.md`

The agreed architecture, proposed by ingest at stage 2a and **approved at a gate** before any page is written:

```markdown
# Narrative — transformer

Core-concept target: 5–8

## Hierarchy
transformer
├── foundations        (word2vec, RNN)
├── attention
├── variants           (multi-head, GQA, sparse, linear)
└── normalization      ← side thread

## Threads
| thread | carries | concepts |
| :-- | :-- | :-- |
| attention-lineage | the central line | foundations → attention → variants |

## Core concepts
| concept | parent | threads | why a page |
| :-- | :-- | :-- | :-- |
| attention | transformer | [attention-lineage] | … |

## Raised at the gate
- tokenization — thread or fold?
- MoE — adjacent (L4) or core?
```

## `materials.md` — the stage-0 inventory

One row per material (a file, or a `##` section of one). Written by `map-materials`.

```markdown
# Materials — transformer

Last updated: YYYY-MM-DD
archive: /abs/path/to/Transformer-materials

Mapped by `/map-materials`. Rows are appended, never rewritten.

Files: 156 · key 22 · redundant 4 · peripheral 12 · off-topic 10

| id | path | kind | role | sha256 | concepts | flags | used-in |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| m007 | `transformer-note.md § Self Attention` | note | key | <hex> | QKV 三个投影的分工 | — | — |
```

| Column | Owner | Rule |
| :-- | :-- | :-- |
| `id` | `map-materials` | `m<nnn>`, stable forever, never reused |
| `path` | `map-materials` | relative to the archive root; a section is `file.md § Heading` |
| `kind` | `map-materials` | `note` / `paper` / `notebook` / `code` / `image` / `slides` / `link-list` / `data` / `other` |
| `role` | `map-materials` | `key` / `redundant-of m<nnn>` / `peripheral` / `off-topic` |
| `sha256` | `map-materials` | hash of the file as read (a `##` section row takes its file's hash); a folder row carries a **manifest digest** of its subtree. The drift anchor |
| `concepts` | `map-materials` | what it teaches, from its content, never its filename |
| `flags` | `map-materials` | `broken-link`, `nested-heading`, `unreadable`, `missing`, `—` |
| `used-in` | `archive-materials` (Writing Assistant) | `<piece> § <section>`, or `—`. Never written by `map-materials` |

**A folder row's manifest digest** (the `sha256` cell of a `path` ending `/**`) is the sha256 of the `«file sha256»\t«archive-relative path»` lines for the folder's covered files, sorted by hash then path, joined by newlines **with a trailing newline**. A mixed folder with individually-rowed exceptions carries the digest and file count of the **remainder** — its subtree minus those exception rows.

Inventory excludes `.DS_Store`, `Thumbs.db`, `*.tmp`, `.git/`, `__pycache__/` and
`.ipynb_checkpoints/`; an archive-local `materials.md` is ordinary input, not the instance output.
Coverage is set equality between eligible physical paths and the union of row-covered paths:
section rows share one physical path; folder rows cover only their remainder. Never add row counts
to file counts. Read-only proof manifests have no inventory exclusions.

On a re-run, compare current file hashes/folder digests with persisted **row** hashes in
`materials.md`, not a deleted prior session manifest. Re-read changed rows; recompute a changed
folder's current remainder and count without claiming which old member changed. Discover new
uncovered paths, retain missing rows and stable ids. `concepts` is preserved by default on existing
rows; report proposed changed descriptions and replace only those explicitly authorized by the
caller (including recorded delegated decisions). Folder counts are derived and may refresh while
preserving the descriptive text. This needs no author-edit marker and preserves foreign columns.

**The cross-product interface, settled.** `materials.md` is one file with disjoint column owners, and `used-in`'s owner (`archive-materials`) lives in Writing Assistant. The write protocol is part of this model, not of either product:

1. **One writer per column.** A writer writes only its own columns and leaves every other column byte-identical. `map-materials` owns everything except `used-in`; `archive-materials` owns only `used-in`.
2. **Adding a writer is adding a column.** A new producer (an MCP endpoint, another tool) takes a new column; it never edits an existing one. No redesign is needed — a column arriving mid-life is a one-time owned fill (point 5).
3. **`used-in` is additive and idempotent per subject.** One token per `<piece> § <section>`, comma-separated; `planned, unused` when a planned material never landed. Re-running the same piece replaces only that piece's tokens, never another piece's, and never the table.
4. **A `map-materials` re-run preserves foreign columns.** It refreshes its own cells and rows and leaves `used-in` untouched.
5. **A late column is a one-time owned migration.** `source-id` — the join key into the cross-topic registry, owned by Information Assistant — is **not** a stage-0 column. When that product first supplies it, its owner adds the column and fills every row once, keyed by `mat:` id, and logs the migration. No other writer touches those cells afterwards.

`used-in` is *evidence about a shipped piece*, so the write happens after the piece ships; `map-materials` runs before. Lint can check the mechanical half: no non-`used-in` cell changes across a re-run.

## `SCHEMA.md`

Bootstrapped by `llm-wiki-ingest` on first run (it replaced `llm-wiki-init`). Sections:

| Section | Holds |
| :-- | :-- |
| Domain | what this instance covers |
| Language policy | body language, term handling, no silent switching |
| Conventions | filenames, wikilinks (min 2 outbound), `updated` bump, index/log pairing |
| Frontmatter | the page field set: `title`, `parent`, `threads`, `levels`, `sources`, `created`, `updated`, optional `contested` / `contradictions` / `confidence` |
| Provenance | the `mat:` / `ext:` rule, version pinning, the two-way `sources:` check |
| Depth template | the L1–L4 semantics and the four coverage values |
| Tags | an **open** list of tags in use, with a preference for reusing one; sprawl is audited, not forbidden |
| Granularity | the fold-first admission rule and the target range |
| Update policy | contradictions: never silently overwrite; keep both positions; `contested: true`; human resolution |

### Bootstrap convention text

Copy the following nine sections verbatim into `SCHEMA.md`, replacing only angle-bracket
placeholders with gate-confirmed instance values (provisional `unknown` before 2a). Add a citation
to the resolved model location/revision. Do not copy the descriptive table as the conventions.

````markdown
# Schema — <domain>

Last updated: <YYYY-MM-DD>

## Domain
This instance covers <domain-and-scope>.

## Language policy
Body language: <language>. Preserve canonical terms and source titles. Never switch language silently.

## Conventions
Pages use flat `wiki/<kebab-case-slug>.md` filenames and `[[slug]]` or `[[slug#anchor]]` links.
Each page has at least two distinct outbound wikilinks. Bump `updated` and a near-top Last updated
date on edits; update index and append an action log entry in the same pass as page writes.
Local asset destinations must render: percent-encode spaces/reserved characters or use `<...>`.
Images need alt text and an existing non-zero image target verified by signature.

## Frontmatter
Required: title, parent, threads, levels, sources, created, updated. Optional: tags, contested,
contradictions, confidence. Lists are lists, dates use YYYY-MM-DD, contested is a boolean.
The root alone uses parent: —; every other parent names a page. Threads names declared threads.

## Provenance
Every claim paragraph, including folds, carries mat: or registered ext: footnotes. Definitions
resolve to materials.md or verified sources.md rows. Sources lists equal used footnote id sets.
Ext rows pin the exact version and the hash of bytes read at registration; never re-fetch for lint.
Mark supplementation visibly. Without material or a verified source, state the gap.

## Depth template
Keep L1 What it is, L2 Relations, L3 Math & code, L4 Extensions, in order, then References.
L1: problem, origin, use cases, core sub-concepts, sourced diagram.
L2: typed relations and core questions. L3: derivation, shapes, reference implementation.
L4: adjacent topics, further reading, open questions. Folded sections go after L4, before References.
Levels are full (all required items), partial (name missing items), stub (pointer/sentence), or
gap (one explicit absence statement). No level body may be empty.

## Tags
Prefer existing tags; the list is open. Maintain the tags in use below.

| tag | pages |
| :-- | :-- |

## Granularity
Fold first. A page must carry a narrative thread, fill L1 fully and L2 meaningfully.
Core-concept target: <N–M>, an agreed assumption reviewed at the gate, not a hard cap.

## Update policy
Keep conflicting positions with their dates and sources; never silently overwrite. Set
contested: true. Contradictions lists other affected page slugs; use [] for a conflict entirely
within this page and name both claims in the body. Resolution requires the author's decision.
````

Bootstrap schema and empty skeletons may precede 2a; no wiki content may precede its gate.
An unchanged-input ingest appends skip entries to `log.md` (and updates its date); every other
file stays byte-identical. Same-page contradictions use `contested: true`, `contradictions: []`.

**The tag list is open, deliberately.** The old closed list was seeded by an interview in `llm-wiki-init`, and the agent now writes `SCHEMA.md` itself — a closed list the agent also authors is self-referential. The sprawl-control purpose survives as an audit: lint reports near-duplicate tags and one-offs, and the agent prefers an existing tag before minting one.

**No `_archive/`.** Superseding a page is the contradiction policy's job; deleting one is git's. `_archive/` was declared in the old SCHEMA and implemented by nothing.

## Invariants

These replace `docs/domain-invariants.md` (ticket **Rewrite the positioning docs** lands the doc; this is the source text).

1. **The archive is read-only.** Nothing is ever written into it — no map, no hash refresh, no rename, no reorganisation.
2. **Every claim traces.** Each paragraph carries a provenance id resolving to a `materials.md` row or a verified `sources.md` row.
3. **No verified source → `gap`.** Content is never invented, and a gap is always explicit.
4. **Provenance survives every stage.** A note keeps its materials' `mat:` ids through dedupe and merge; a page keeps its notes' provenance through writing.
5. **A page exists only for a threaded concept** that can fill L1 and L2. Everything else folds.
6. **One canonical production instance per domain**, external to this repository. Explicitly authorized acceptance runs may use isolated sibling instances; they are not additional production authorities. Instance data is never packaged, never a repository fixture.
7. **One canonical implementation per skill.** A stage has exactly one owner.
8. **AKB never writes learner state.** Attempts, mastery and evidence belong to Learning OS.

## Boundaries

| Product | Relation |
| :-- | :-- |
| **Information Assistant** | Upstream. Discovers sources, owns the cross-topic source registry and the trust axis. Its outputs can become raw input here. |
| **Learning OS** | Downstream. Reads wiki pages as study material; owns attempts and mastery. **Never written to by AKB.** |
| **Writing Assistant** | Downstream. Takes wiki pages and `materials.md` as sourced material; owns `archive-materials` and the `used-in` column. |
| **Synapse** | Derived cross-source index over published wiki pages. |

## Deferred

- **Cognitive compounding** (stage 2 of the product's goals). Only the draft extraction from the old `TODO.md` is preserved, as input to that design.
