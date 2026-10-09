# Knowledge pipeline skills

Last updated: 2026-10-09

The four skills in this directory are **stages of one pipeline**, not four independent tools. They turn a folder of raw material into a concept wiki whose every claim is traceable to that material or to a verified primary source.

The domain model is frozen in [docs/knowledge-model.md](../../docs/knowledge-model.md). That file is the single source of truth: **change the model first, then the skills.** [CONTEXT.md](../../CONTEXT.md) is its glossary.

```
archive/  ──map-materials──▶  materials.md  ──clean-notes──▶  notes/  ──llm-wiki-ingest──▶  wiki/
 (external,      stage 0:         (evidence)     stage 1:        (evidence)     stage 2:        (presentation)
  read-only)      inventory                      structure                     narrative
                                                                                   │
                                                          llm-wiki-lint ───────────┘
                                                          stage 2 audit (read-only)
```

## The four stages

| Stage | Skill | In → out | Gate | Writes |
| :-- | :-- | :-- | :-- | :-- |
| 0 | `map-materials` | an absolute archive path + `$KB_PATH` + topic → `materials.md` | off-topic exclusions | `materials.md` — every column except `used-in` |
| 1 | `clean-notes` | `$KB_PATH` + `materials.md` + the archive → `notes/<topic>.md` | the MECE outline | `notes/` |
| 2 | `llm-wiki-ingest` | `$KB_PATH` + `notes/` + `materials.md` → `wiki/<slug>.md`, plus `SCHEMA.md`, `narrative.md`, `sources.md`, `index.md`, `log.md` | 2a narrative; 2c page diff | the whole instance except stage 0/1 output |
| — | `llm-wiki-lint` | `$KB_PATH` → a report + the exact `log.md` line | none (read-only) | **nothing** |

Each stage is a separate run with its own gate, and each stage is **complete before the next starts**: stage 1 cannot begin until `materials.md` exists, stage 2 cannot begin until `notes/` exists. What passes forward is an **artifact with provenance ids attached**, never raw reasoning:

| Stage | Reads | Adds |
| :-- | :-- | :-- |
| 0 | the archive | `materials.md` — the ids every later stage cites |
| 1 | `materials.md` + the archive | `notes/` — the material restructured, ids carried through |
| 2 | `notes/` + `materials.md` | `wiki/` — concepts explained, ids carried through, `ext:` ids added |
| audit | the whole instance + the archive | nothing |

Stage 1 re-reads the archive because a note must be written from the material itself; stage 2 does not, because a page is written from the notes. The archive is also the only thing never written to, at any stage.

## What each stage owns, and what it must not become

The stages exist separately because they answer different questions, and collapsing any two loses either traceability or readability.

**`map-materials` — an inventory.** One row per material (a file, or one `##` section of one), with a stable `mat:m<nnn>` id, a `sha256` drift anchor, a `role` (`key` / `redundant-of m<nnn>` / `peripheral` / `off-topic`), `concepts` read from content and never from the filename, and `flags`. It writes `materials.md` **into the instance, never into the archive** — the archive is external and read-only, and this stage proves it by asserting no archive file is newer than the session start. It never judges quality, never fills `used-in`, and never deletes a row: a material that disappears keeps its row and gains `missing`.

**`clean-notes` — evidence.** The top-level MECE topics *are* the notes: one `notes/<topic>.md` per topic, each merging blocks from any number of files and genres (a sub-topic is a `##` inside its note, never a second file), two levels only, one `notes/misc.md` catch-all whose growth past ~15% of the material means a topic is missing. It deduplicates on the skill's own classification (verbatim / near-duplicate / recurrence — recurrence is *not* duplication), and **a block may not be merged unless the note retains which `mat:` rows the merged content came from**. It adds nothing, improves nothing and judges nothing: a note reports what the material says.

**`llm-wiki-ingest` — presentation.** It bootstraps `SCHEMA.md` on a first run (this replaced the retired `llm-wiki-init`), proposes `narrative.md` at the 2a gate, verifies and registers primary sources in `sources.md`, then writes per-concept pages. A concept earns a page only if it **both** carries a thread in `narrative.md` **and** can fill L1 fully and L2 meaningfully — otherwise it folds into the page that owns it as a `##` section. When uncertain, fold. The instance declares a core-concept target range (Transformer: 5–8) and exceeding it is raised at the gate.

**`llm-wiki-lint` — audit.** Read-only over the result: the L1–L4 coverage matrix, the two-way `sources:` check, footnote resolution, `ext:` verification, `narrative.md` ↔ pages consistency, `index.md` completeness, concept-map MECE, orphans, broken links, frontmatter, tag sprawl, language, confidence, `materials.md` sha256 drift against the archive, and `used-in` grammar. It holds nothing and gates nothing: it reports findings and **prints** the `log.md` line for the caller to append.

## How provenance survives the chain

This is the property the pipeline exists to protect, and it is why the stages are not merged:

```
material file ──▶ mat:m007 ──▶ note paragraph cites mat:m007 ──▶ page paragraph cites mat:m007 + ext:vaswani-2017
                        │                                              │
                        └── sha256 drift anchor                        └── sources.md row: url, version, fetched_at, sha256
```

- **Every paragraph carries at least one provenance id.** `mat:` points at a `materials.md` row; `ext:` points at a verified `sources.md` row. Provenance is per-paragraph, not per-page.
- **`ext:` ids must be verified**, with the exact version read recorded (`1706.03762` has seven versions — "the paper" is ambiguous and insufficient). Verification happens once, at registration.
- **No verifiable source → `levels: Lx: gap`,** with one explicit statement naming what is missing. Inventing content is the one unrecoverable failure.
- **`sources:` on a page is a two-way index**, enforced by lint: every footnote id appears in it, and every entry in it is used by a footnote.

## Gates

Every run stops at a gate before writing, because the granularity and the exclusions are decisions, not derivations:

| Gate | Shows | Blocks |
| :-- | :-- | :-- |
| stage 0 | the off-topic exclusion list | writing `materials.md` |
| stage 1 | the MECE outline: the note list with definitions and source counts, each note's `##` sub-headings, duplicate clusters, any proposed `ext:` supplement, the image re-path plan | writing `notes/` |
| stage 2a | `narrative.md`: hierarchy, threads, core-concept list, target range, and the questions worth raising | source verification and page writing |
| stage 2c | the diff summary: page list with `parent`/`threads`, expected coverage, `ext:` ids registered | writing pages |

Re-runs gate only what changed — stage 1 re-gates only the notes whose source set or outline changed, and names the unchanged ones.

## The one writer outside this directory

`materials.md` has **disjoint column owners**, and one of them lives in another product:

- `map-materials` owns every column except `used-in`.
- `archive-materials` — which moved to **Writing Assistant** — owns only `used-in`, recording which shipped piece used which material (`<piece> § <section>`, or `planned, unused`).

The protocol is part of the knowledge model, not of either product: **one writer per column; adding a writer means adding a column, never editing an existing one; `used-in` is additive and idempotent per subject; a `map-materials` re-run leaves foreign columns byte-identical.** A late column (Information Assistant's `source-id` join key into the cross-topic registry) is a one-time owned fill, not a redesign.

## Where this pipeline sits

| Product | Relation |
| :-- | :-- |
| **Information Assistant** | Upstream. Discovers sources; owns the cross-topic source registry and the trust axis. Its output can become archive material here. |
| **Writing Assistant** | Downstream. Takes wiki pages and `materials.md` as sourced material, and owns `archive-materials` plus the `used-in` column. |
| **Learning OS** | Downstream. Reads wiki pages as study material; owns attempts and mastery. **These skills never write learner state.** |
| **Synapse** | Derived cross-source index over published wiki pages. |

## Running them

The instance root is always an explicit parameter (`$KB_PATH`) — never a default — and the archive path is recorded in `materials.md`'s header, so no skill hard-codes a path:

```
map-materials   →  clean-notes  →  llm-wiki-ingest  →  llm-wiki-lint
   (gate)            (gate)          (2a + 2c gates)
```

Each skill is independently installable and cites [docs/knowledge-model.md](../../docs/knowledge-model.md) rather than restating it, so a skill's own `SKILL.md` is the authority on its steps and this file is only the map of how they connect.
