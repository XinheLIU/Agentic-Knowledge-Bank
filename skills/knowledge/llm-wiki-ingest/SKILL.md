---
name: llm-wiki-ingest
description: "Stage 2 of the knowledge pipeline: turn notes/ into a provenance-tracked concept wiki. Bootstraps the instance (SCHEMA.md) on its first run, proposes narrative.md at a gate (hierarchy, threads, core-concept target range), verifies and registers primary sources in sources.md, then writes per-concept pages with parent/threads frontmatter, all four L1–L4 depth sections with explicit coverage (full|partial|stub|gap), and a mat:/ext: footnote on every paragraph. Never invents content, never writes into the archive, never writes learner state. Use for 'ingest these notes', 'build the wiki', 'write the concept pages', 'propose the narrative', or as stage 2 after clean-notes."
license: MIT
metadata:
  hermes:
    tags: [knowledge-base, wiki, narrative, provenance, ingest]
    category: knowledge
    related_skills: [map-materials, clean-notes, llm-wiki-lint]
---

Last updated: 2026-10-09

# LLM Wiki — Ingest (stage 2)

Stage 2 of the pipeline in [docs/knowledge-model.md](https://github.com/XinheLIU/Agentic-Knowledge-Bank/blob/main/docs/knowledge-model.md):
`notes/` in, `wiki/` out, in **three sub-stages** — 2a proposes the narrative, 2b verifies and
registers primary sources, 2c writes the pages. Two human gates, one at each end. On the instance's
first run this skill also **bootstraps the instance** (`SCHEMA.md`, and the empty skeleton of
`narrative.md`, `sources.md`, `index.md`, `log.md`).

**Announce at start:** "I'm using the llm-wiki-ingest skill to build the concept pages from `notes/`."

**When to run:** after `clean-notes` has produced `notes/`, and after `map-materials` has produced
`materials.md` (the archive inventory whose `mat:` ids the notes carry). Re-run it whenever `notes/`
changes; unchanged notes are skipped, not re-derived.

The distinction that governs everything here: **a note is evidence, a page is presentation.** The
note reports what the material says. The page explains a concept to a reader, at four depths, in the
order the narrative gives. That difference is the reason both layers exist, and it is why a page is
never written by copying a note.

## Normative dependency (source and deployed copies)

Read the canonical model before acting. Use explicit `KB_MODEL_ROOT` when supplied: read
`$KB_MODEL_ROOT/docs/knowledge-model.md` and `$KB_MODEL_ROOT/CONTEXT.md` (the glossary is at
repository root). In a source checkout, the repository containing this skill is that root.
A flattened installed copy must **not** resolve `../../../docs/` from its install directory.
Without a checkout, read `docs/knowledge-model.md` and `CONTEXT.md` from
`https://github.com/XinheLIU/Agentic-Knowledge-Bank` at the installed source revision recorded by
the installer; if unavailable, use `main` and record that revision choice explicitly. Record the
resolved location/revision or working-tree hash in the run report. Never vendor another canonical
copy or proceed without reading the contract; report an unavailable dependency before writes.

Gates follow the model's caller-authorization rule: with explicit unattended delegation, record
question, options, choice and reason in the existing report/log and continue within that scope.

## Invocation and inputs

| Input | Rule |
| :-- | :-- |
| `$KB_PATH` | **Required, explicit, never a default.** The instance root. The archive is found through `materials.md`'s `archive:` header — never hard-code a path. |
| `notes/` | The evidence, one topic per file. Read-only to this skill. |
| `materials.md` | Stage 0. Read for `mat:` ids and their `sha256`. **Never rewritten here.** |
| `$KB_PATH/sources.md` | The provenance registry. 2b appends verified rows. |
| `$KB_PATH/narrative.md` | The agreed architecture. Absent on the first run — 2a proposes it at the gate. |

This skill writes only: `wiki/<slug>.md`, `index.md`, `log.md`, the bootstrapped `SCHEMA.md`,
`sources.md`, and `narrative.md`. It **never** writes into the archive, `notes/`, `materials.md`,
`learning/`, or learner state. The archive is external and read-only, absolutely — there is no
capture step and no `raw/` directory; nothing is copied or anchored.

## Orientation (before any sub-stage)

Read, in this order: `SCHEMA.md` → `narrative.md` → `sources.md` → `index.md` → the last 30 lines of
`log.md` → `notes/`. **Bootstrap before acting, never act without conventions.**

**Bootstrap (first run only).** When `$KB_PATH/SCHEMA.md` is absent, this run bootstraps the
instance. Write `SCHEMA.md` with all nine sections, taking their **convention text verbatim from
`docs/knowledge-model.md` § `SCHEMA.md` → Bootstrap convention text** and citing it — the model stays the single source, this
skill does not re-invent it. Replace only the template's instance placeholders; the table below
is a checklist, not the convention prose:

| Section | Holds |
| :-- | :-- |
| Domain | what this instance covers (provisional until the 2a gate) |
| Language policy | body language, term handling, no silent switching |
| Conventions | filenames, wikilinks (min 2 outbound), `updated` bump, index/log pairing |
| Frontmatter | `title`, `parent`, `threads`, `levels`, `sources`, `created`, `updated`, optional `contested` / `contradictions` / `confidence` |
| Provenance | the `mat:` / `ext:` rule, version pinning, the two-way `sources:` check |
| Depth template | the L1–L4 semantics and the four coverage values |
| Tags | an **open** list of tags in use — starts empty |
| Granularity | the fold-first admission rule and the target range |
| Update policy | contradictions: never silently overwrite; keep both positions; `contested: true`; human resolution |

Also create the empty skeleton of `narrative.md`, `sources.md` (header + table header only),
`index.md` and `log.md`, and `wiki/`. Never create or touch `notes/`.

**No domain interview.** Derive the Domain from the instance folder name and the `narrative.md`
title, and the language policy from the predominant language of `notes/`. Both are **confirmed at the
2a gate**; an unreadable or absent signal is recorded as `unknown` with the policy "never switch
language silently" — never guessed. On the first run the confirmed values are written into `SCHEMA.md`
as part of the bootstrap pass; after that **`SCHEMA.md` is append-to-Tags only** — no other section
is rewritten by a later run. A later run that finds the gate-confirmed Domain or Language policy
wrong returns to the 2a gate and rewrites that one section, recording the confirmation; the
append-only rule governs incidental runs, not a gate-confirmed correction.

**Tags are open, and the list is maintained.** The Tags section is a list of tags *in use*, with a
preference for reusing one. Write it as a two-column `tag | pages` table (`pages` = comma-separated
slugs; a one-off reads as a single row). When 2c mints a tag that is not on the list, append it to
`SCHEMA.md` in the same pass as the page that used it, bumping `Last updated`. Sprawl is **audited,
not forbidden** — `llm-wiki-lint` reports near-duplicate tags and one-offs; this skill just prefers
an existing tag first. There is no `_archive/`; superseding is the contradiction policy's job and
deleting is git's.

## Sub-stage 2a — propose `narrative.md` (GATE)

The agreed architecture, approved before any page is written. This is where granularity is decided.

Propose, then stop and wait:

````markdown
# Narrative — <domain>

Core-concept target: 5–8
root page: transformer      # the one page with `parent: —`

## Hierarchy
transformer (domain)
└── transformer            ← root page, parent: —
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
````

**The target range is proposed, not fixed.** Derive a candidate `Core-concept target: N–M` from what
stage 1 actually produced — the number of notes, the number of distinct concepts, the breadth of the
hierarchy — and write it into the draft. The user amends it at the gate like everything else. When
the proposed concept count later falls outside the range, it is **raised at the gate again** — the
range is a checked assumption, not a hard cap. Exceeding it is a signal to fold.

**Page admission is fold-first.** A concept earns a page only if it satisfies **both**:

1. **it carries a thread** in the narrative, and
2. **it can fill L1 fully and L2 meaningfully** from the available material.

Otherwise it **folds into the page that owns it**, as a `##` section placed after the four level
sections and before `## References` (`levels:` covers L1–L4 only). **When uncertain, fold** —
under-splitting is cheap to fix later; over-splitting scatters one idea across thin stubs. A
sub-variant gets its own page only when the gate agrees. The proposed core-concept list is always
shown here, with every concept's `parent` and `threads`.

**The root page carries `parent: —`.** `—` is the domain root and the only non-page `parent:`
value. `narrative.md` declares `root page: <slug>` once and labels the domain with a suffix
(`transformer (domain)`) so it never collides with the root page's slug; every other `parent:` names
a page slug.

**Nothing is written past 2a's own gate until the user approves or amends.** Batch waiver: when the
run is a pre-approved batch, the user may waive the gate once, up front — say so in the log entries.

## Sub-stage 2b — enrich: verify and register primary sources

The pages are sourced from `notes/`; this sub-stage finds the **authoritative outside sources** that
let a level say more than the notes can, and registers only what genuinely verifies.

**Candidate sourcing — propose, confirm, then verify.**
1. Collect candidates from the notes' **own cited works** — read the note bodies' prose and inline
   links **and** any `## Supplementation (ext:)` block. Stage 1's supplement ids/metadata are
   provisional handoff candidates; this stage alone writes `sources.md`. Verify the exact claim
   and version before registering, or reuse an existing verified row for the same work/version.
   On failed verification, omit the supplement from pages and name the missing coverage; never
   repair the note. If a proposed id collides with another work/version, allocate a new page-side
   id and log the candidate → registered id mapping.
2. Add a **bounded search** for the canonical work behind a concept the narrative admits but the
   notes only sketch.
3. Show the candidate list to the user inline — one line per candidate: title, why, the concept it
   serves. This is a list-level confirm, **not a third gate**; adjust and proceed.
4. Verify each approved candidate. Only verified ones become rows.

**"Verified" means identity and version are determinable — not merely "fetch succeeded."**

| Step | Rule |
| :-- | :-- |
| Locator | fetch the **canonical** locator (e.g. `https://arxiv.org/abs/1706.03762`), never a mirror |
| Identity + version | resolve the exact version read — the arXiv `vN`, the doc edition, the repo tag. **No determinable version → no row**, and the page that needed it records `gap` |
| Payload | `url` (the exact locator fetched), `version`, `fetched_at` (today), `sha256` of **the bytes actually read** — recorded once at registration and never re-verified, because a live page is not byte-stable — and `verified: ✅` |
| Kind | `primary` (the work itself) or `secondary` (an exposition: textbook, course notes). **Not `tier`** — trust is a different axis, owned across topics by Information Assistant |
| Reuse | an existing `sources.md` row for the same work **and** the same version is reused as-is. A **different version is a new row and a new id**, never a silent overwrite |
| Persistence | the fetched body is **stored nowhere** — no `raw/`, no instance temp, no archive write. The hash records what was read; it is not an artifact |

```markdown
# Sources — <domain>

Last updated: YYYY-MM-DD

| id | kind | title | url | version | fetched_at | sha256 | verified |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| vaswani-2017 | primary | Attention Is All You Need | https://arxiv.org/abs/1706.03762 | v7 | 2026-10-08 | <hex> | ✅ |
| d2l-11.7 | secondary | Dive into Deep Learning §11.7 | https://d2l.ai/… | 1.0.3 | 2026-10-08 | <hex> | ✅ |
```

**No verifiable source → `gap`, not invention.** A work that cannot be verified (no stable locator,
a gated landing page, no version) is **left out** — it never gets a row, and the level that wanted it
is marked `gap` and named at the gate. Append rows additively; a re-run leaves every existing row
byte-identical.

## Sub-stage 2c — write the pages (GATE)

**Show the diff summary, wait, then write.** One line per page, no prose:

| Page | Action | parent | threads | planned levels: | fed by | cites |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| attention | create | transformer | [attention-lineage] | L1 full · L2 full · L3 partial · L4 gap | notes/attention.md | mat:m007, mat:m012, ext:bahdanau-2014, ext:vaswani-2017 |
| transformer | update | — | [attention-lineage] | … | notes/transformer.md, notes/variants.md | … |

Plus, separately: the **contradictions found**, and the **coverage counts** across the planned page
set (`full N · partial N · stub N · gap N`), so a page set that is mostly `gap` is visible before
anything is written.

**Deviation rule — a run cannot smuggle in an unapproved page.** If writing turns up a concept
absent from the approved narrative, or a contradiction the diff did not list, **stop and return to
the gate**: a short 2c addendum for a page-level addition, or back to 2a when the narrative itself
must change. Nothing is written past the gate that the gate did not see. `mat:` ids added during
writing are evidence-level and never return to the gate; a new `ext:` row or a page is gate-worthy.

Then write, in one pass, and update the pair in the same pass:

- **`wiki/<slug>.md`** — the concept page, flat under `wiki/`, from the template below.
- **`index.md`** — header `# Index — <domain>`, `Last updated: YYYY-MM-DD`, `Total pages: N`; one
  `## <thread>` section per declared thread in narrative order; under it `- [[slug]] — <one-line
  summary>. \`parent: <x>\``. A page with several `threads:` is listed under its **first declared**
  thread with the rest in parentheses. Bump `Last updated` and `Total pages`; a coverage table
  mirroring `levels:` may follow.
- **`log.md`** — append (see below).

### The concept page

Every page has these body sections, **in this order, always** — a missing section is a `gap`, never
an omission:

````markdown
---
title: Attention
parent: transformer
threads: [attention-lineage]
levels: {L1: full, L2: full, L3: partial, L4: gap}
sources: [mat:m007, mat:m012, ext:bahdanau-2014, ext:vaswani-2017]
created: 2026-10-08
updated: 2026-10-08
contested: true                 # optional
contradictions: [self-attention]  # optional
confidence: high                # optional
---
## L1 · What it is
problem solved, origin (who/when), use cases, core sub-concepts, diagram[^mat:m007]
## L2 · Relations
[[links]] with a relation type (generalizes / variant-of / prerequisite / contrasts) + core questions[^mat:m007]
## L3 · Math & code
derivation, shapes, reference implementation[^ext:vaswani-2017]
## L4 · Extensions
adjacent topics, further reading, open questions
## References
[^mat:m007]: materials.md m007 — `transformer-note.md § Self Attention`
[^ext:vaswani-2017]: sources.md vaswani-2017 (v7) — Attention Is All You Need
````

No `type:` field and no `entities/ concepts/ comparisons/ queries/` directories — a page's identity
is its position in the concept graph (`parent` + `threads`) and its slug. Sub-variants are `##`
sections inside their parent, placed after L4 and before `## References`; the root page carries
`parent: —`.

**The four levels.** `## L1 · What it is` — what problem, what origin, what it is made of (notes,
and primary sources). `## L2 · Relations` — how it connects and what to ask next (notes + narrative).
`## L3 · Math & code` — the derivation, the shapes, a reference implementation (notes, supplemented
from primary sources). `## L4 · Extensions` — what is adjacent and what is open (primary sources,
explicitly marked as beyond the raw).

**Asset preservation.** Keep destinations valid under the model's Assets and audit scope rule:
percent-encoded or angle-bracket paths, non-empty alt, provenance retained. Before completion,
render every page image and verify decoded local targets, size and image signature (lint L4's
checker or equivalent). Never turn an encoded note path back into raw-space Markdown.

**Coverage, not content.** `levels:` records coverage with exactly four values:

| Value | Meaning |
| :-- | :-- |
| `full` | every required template item is supported, including L1's sourced diagram |
| `partial` | answers it in part; the page says what is missing |
| `stub` | a pointer to where it belongs, or a single sentence |
| `gap` | no material and no verified source exists |

**All four `## L1 … ## L4` headings always exist.** A level is never left empty under any value. A
`gap` body is **one explicit statement naming what is missing** (a single block, possibly wrapped) — never silently empty, never filled by
invention. `partial` and `stub` are honest self-assessments, not failures.

**Provenance is per paragraph, and every paragraph carries at least one id.**

- `mat:m007` → a row in `materials.md`.
- `ext:vaswani-2017` → a row in `sources.md`.
- **Version pinning is mandatory.** Where a work has multiple versions, the id resolves to a row
  recording the exact version read (`v7`). "The paper" is ambiguous and insufficient.
- **Supplemented content is visibly distinct** from note-derived content.
- **`sources:` is the page's provenance index, checked both ways:** every footnote id on the page
  appears in `sources:`, and every entry in `sources:` is used by at least one footnote.
- **An image inside a folded folder row** is cited with the folder row (`mat:m0NN`) plus the note row
  whose body carried the reference, so the aggregation stays traceable.
- `updated` and a near-top `Last updated` date are bumped on every edit; minimum 2 outbound `[[wikilinks]]` per page.

**Contradictions — never silently overwrite.** Keep both positions with their dates and sources
(per-paragraph footnotes now make those expressible), set `contested: true` — a **bare boolean** —
and `contradictions: [other-page-slug]` for cross-page conflicts. For a conflict entirely within
one page, use `contradictions: []`, name both claims in its body, and tell the user. These require human resolution before
claims harden into accepted fact. `llm-wiki-lint` surfaces them for resolution.

**The gap-vs-fold asymmetry.** A gap is a normal, always-acceptable outcome: write it and continue.
But a **`gap` on L1 or L2 is a page-admission failure** — admission requires filling L1 fully and L2
meaningfully. So it does not block the run: it is surfaced at the 2c gate as **"admission failed —
consider folding it into `<parent>`"**, and the user resolves it by approving the fold (the concept
becomes a `##` section of its parent) or by accepting the gap explicitly. `L3`/`L4` gaps need no
special handling, and `L4` is expected to be `partial`/`stub`/`gap` routinely. 2b gets **one bounded
enrichment attempt** for a level whose `ext:` need is identifiable — one search round, at most three
candidates, registering only those that verify — then an honest `gap`, never an open-ended retry loop.

**Structural rewrites are never automatic.** Never auto-merge and never auto-graduate: folding and
splitting rewrite prose and are human decisions, always taken at the gate.

### Subagents extract; they never write

For a large `notes/` set, dispatch one subagent per note (or per confirmed concept cluster) and have
each return **only a candidate table** — `Paragraph | Candidate concept | Verdict (create/update/fold)
| Target page | Why`. The **parent merges the tables, resolves conflicts, and writes every file.**

- Assignment needs the **whole note in view**: mapping must run over the full note first, because a
  subagent seeing one section cannot know a paragraph belongs under a concept three sections away.
- One note feeds one to several pages, and a page may cite paragraphs from **more than one note**.
  The mapping is never the reverse.
- No subagent writes. This division is instruction-only; no mechanism enforces it, so it is stated
  in every dispatch.

### Skip-on-unchanged

Re-run over unchanged input is idempotent. The identity is **not** a filename and **not** an archive
hash — the archive hash is `map-materials`'s job, read from `materials.md`. A note whose recorded
content hash (in the last `log.md` ingest entry) is unchanged and whose derived pages all still exist
is skipped: the run writes one `skip` log line and stops for that note. A changed or new note
re-derives only the pages it feeds. Never refresh a page just to look busy.
On a skip-only run, update only `log.md` and its Last updated date; defer log rotation to a writing
run so the unchanged-output contract has exactly one exception.

## Hard Rules

1. **Never invent content.** No verified source and no material → `gap`, named explicitly. This is
   the one unrecoverable failure.
2. **Never write into the archive**, `notes/`, or `materials.md`. Prove the archive is untouched with
   the same manifest diff and `find -newer` assertion `map-materials` defines — capture a marker
   before any read and assert nothing in the archive is newer at the end.
3. **Never write wiki pages before the 2a gate, and never write past the 2c gate** without showing
   the diff. The batch waiver exists at 2a only.
4. **Never write a page whose four `## L1 … ## L4` sections are not all present**, each either filled
   or carrying its named `gap` line.
5. **Never let a footnote dangle**: every `mat:`/`ext:` id resolves to a row, and version pinning is
   mandatory.
6. **Never silently overwrite on contradiction** — keep both positions, `contested: true`, tell the
   user.
7. **Never create or update a page without updating `index.md` and `log.md` in the same pass.**
8. **Never reuse an id, and never rewrite a `sources.md` row** — a different version is a new row.
9. **Never mint a tag before checking the `SCHEMA.md` list**; append new tags in the same pass.
10. **Never call a service API.** This skill is files, plus the single outbound read of 2b's
    verification fetch. No wiki HTTP API, no database, no service integration.
11. **Never write to Learning OS `learning/`** — the wiki/learning wall. Learner evidence is never
    written here.
12. **Never commit.** Suggest the commit; never run it.

### `log.md` — append-only

Keep a near-top `Last updated` date; entries remain append-only. Header format `## [YYYY-MM-DD] action | subject`; rotate to `log-YYYY.md` past 500 entries. One entry
per sub-stage that wrote, plus skips and the bootstrap:

```markdown
## [YYYY-MM-DD] ingest | <domain> — 2c pages
- Notes: notes/attention.md sha256:<hex>, notes/variants.md sha256:<hex>
- Created: [[attention]], [[multi-head-attention]]
- Updated: [[transformer]] (added normalization section)
- Folded: [[rope]] → transformer § RoPE
- Contested: [[attention]] ↔ [[self-attention]]
- Coverage: full 6 · partial 3 · stub 1 · gap 1
```

## Contract test

Given a fixture instance (`materials.md`, two `notes/` files, no wiki yet) with a concept that has
material for L1–L3 and nothing for L4, and one note that contradicts a claim in the other:

- the first run bootstrapped `SCHEMA.md` with all nine sections and an **empty** Tags list, plus the
  `narrative.md` / `sources.md` / `index.md` / `log.md` skeletons — and it wrote nothing into the
  archive or `notes/`;
- the 2a gate printed the hierarchy, threads, core-concept list and a **proposed target range**, and
  no wiki content was written before it was answered; Orientation bootstrap/skeletons are allowed;
- the 2b candidate list was shown and confirmed before any row was registered; every registered row
  has `url`, `version`, `fetched_at`, a 64-hex `sha256` and `verified: ✅`; a candidate with no
  determinable version produced no row and its level is `gap`;
- the 2c gate printed one line per page with `parent`/`threads`/planned levels/feeding notes/cited
  ids, the contradictions, and the coverage counts, and wrote only after it was answered;
- every created page carries all four `## L1 … ## L4` sections, `levels:` uses only
  `full|partial|stub|gap`, the L4 body is a single named gap line, and every paragraph carries a
  `mat:`/`ext:` footnote whose id appears in `sources:` **and** vice versa;
- the contradiction set `contested: true` (a bare boolean) plus `contradictions: [...]`, kept both
  positions, and reported to the user;
- `index.md` has one entry per page and the bumped header; `log.md` gained one appended entry per
  sub-stage and no earlier entry changed;
- a second run over unchanged notes adds no page, writes a `skip` log line, and leaves every file
  byte-identical except `log.md` (skip entries and its Last updated date).

## Handoffs

**In:** `$KB_PATH` explicit; `notes/` (stage 1 evidence); `materials.md` (stage 0, for the `mat:`
ids). Nothing else.

**Out:** `wiki/<slug>.md` concept pages → `llm-wiki-lint` audits the coverage matrix, footnote
resolution and `sources.md` two-way check; Learning OS and Writing Assistant read the pages
downstream (read-only). `index.md` is the query front door; `log.md` is the action record.

**Boundaries:**
- vs `map-materials`: that inventories the archive into `materials.md` with `mat:` ids and sha256;
  this reads those ids and never refreshes inventory hashes. Read-only archive hashing for
  before/after proof is required and does not change inventory ownership.
- vs `clean-notes`: that is stage 1 — evidence, one note per topic, deduplicated with provenance
  kept. This is stage 2 — presentation; it never edits a note and never re-derives one.
- vs `llm-wiki-lint`: that is read-only and reports; this writes. Lint never writes a page, and this
  skill never "fixes" a finding by rewriting on lint's behalf — structural changes go through the
  gate.
- vs `archive-materials` (Writing Assistant): that owns `materials.md`'s `used-in` column and runs
  after a piece ships; this skill never writes that column.
- vs Learning OS: this skill never writes `learning/` or any learner state.
