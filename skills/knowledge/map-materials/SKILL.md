---
name: map-materials
description: Rank a raw materials folder once, for every downstream reader — one row per file recording what it is, which registry source it belongs to, whether it is key, redundant, or peripheral, and what it actually teaches. Writes materials.md at the archive root and nothing else. Tier 2, workflow, ~45 min. Use for "map these materials", "整理素材", 素材分级, 材料处理, or before /survey on a topic whose archive has never been processed.
---

Last updated: 2026-10-02

# Map Materials

## Overview

A folder of accumulated material in, **one map** out: `materials.md` at the folder root, one row
per file, saying what the file is and how much of it is worth anyone's attention.

**When to run:** After topic is confirmed (via `/pre-write-grill` or explicit author statement), not
before. The confirmed topic focuses which materials get deep treatment vs light categorization.

This runs **once per archive**, after framing starts — not once per reader, and not before the
topic is known. Today `/survey`, `/curriculum`, and `frame` each scan the same folder cold and each
reach their own private conclusion about what matters in it. Three scans, three answers, none of
them written down. The map replaces all three: every downstream skill reads a row instead of
re-deriving it, and when a judgment is wrong it is wrong in one place, visibly, where it can be
fixed.

The map is **processing, not curation**. It says "these five notebooks are the same notebook" and
"this folder is about vision, not this topic". It does not say what the chapter will use (that is
`develop-examples`' selection map) or how good the source is (that is `sources/<domain>.md`).

## The archive is read-only

The materials folder belongs to the archive layer: large, unversioned, cloud-synced, and full of
files the author did not write. Exactly two things may be written into it, ever:

| Write | By | When |
| :--- | :--- | :--- |
| `materials.md` | this skill (rows), `archive-materials` (`used-in`, renames) | at mapping, then after a piece ships |
| confirmed renames | `archive-materials` only | after a piece ships, in one batch |

Everything else — no moves, no deletions, no `.DS_Store` sweeps, no reorganized folders, no
rewritten notes. A folder that genuinely needs a different tree is `/organize-docs`, and that is a
separate, explicit decision by the author.

## Hard Rules

1. **Never write into the folder except `materials.md`.** Prove it at the end with the `find -newer`
   check in Step 5.
2. **Every file is covered by a row** — its own, or an ancestor folder's. A file nobody rowed is
   the one that turns up unexplained in three months.
3. **A duplicate is `redundant-of <id>`, never deleted and never omitted.** Name the canonical row.
   Which copy is canonical is a judgment: prefer the one with the better filename, then the one in
   the better-named folder.
4. **`concepts` comes from the file's content, never from the filename** — for every `key` row. A
   `peripheral` or `redundant-of` row may be described from its filename and folder, because
   nothing downstream will teach from it.
5. **Never fill `used-in`.** That column is evidence about a shipped piece, and `archive-materials`
   owns it. At mapping time every `used-in` cell is `—`.
6. **A re-run appends and refreshes; it never rewrites.** New files get new ids; existing rows keep
   their id, their `used-in`, and any `concepts` the author edited. Ids are never reused.
7. **A peripheral *folder* gets one row, not one per file** — with its file count and the one line
   saying why the whole folder shares the fate. A loose file that is off-topic still gets its own
   `peripheral` row; the rule is against exploding a folder, not against the role.
8. **Say what you could not open.** A binary you did not read, a PDF you only took the title from —
   the row says so. A guessed `concepts` cell is worse than an empty one.

## The map

`<archive-root>/materials.md`:

````markdown
# Materials — <topic>

Last updated: YYYY-MM-DD

Mapped by `/map-materials`. Rows are appended, never rewritten. `used-in` is filled by
`/archive-materials` after a piece ships.

Files: <n> · key <n> · redundant <n> · peripheral <n>

| id | path | kind | source-id | role | concepts | used-in |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| m001 | `transformer-note.md § Self Attention` | note | — | key | QKV 三个投影的分工；打分—softmax—加权求和 | — |
| m002 | `03-Core-Papers/Attention is All you Need.pdf` | paper | vaswani-attention | key | 原始架构；§3.2 scaled dot-product 与 √d_k 的论证 | — |
| m003 | `03-Core-Papers/09 - Attention Is All You Need.pdf` | paper | vaswani-attention | redundant-of m002 | same paper, second copy | — |
| m004 | `06-Vision/**` (10) | paper | — | peripheral | ViT and the vision branch — a different topic's chapter | — |
````

### Columns

| Column | Rule |
| :--- | :--- |
| `id` | `m<nnn>`, unique within this map, stable forever. Referenced by `develop-examples`' selection map |
| `path` | relative to the archive root. A note is rowed **per section** (`file.md § Heading`) when its sections have different fates; a folder row ends in `/**` and carries its file count |
| `kind` | `note` \| `paper` \| `notebook` \| `code` \| `image` \| `slides` \| `link-list` \| `data` \| `other` |
| `source-id` | the `sources/<domain>.md` row this file is a copy or part of; `—` when the file is the author's own or the source is unregistered |
| `role` | `key` \| `redundant-of m<nnn>` \| `peripheral` |
| `concepts` | what this file actually teaches, in one line. Free text until `/survey` names nodes |
| `used-in` | `<piece> § <section>`, or `—`. Never written here |

### The three roles

- **`key`** — a downstream reader should open this. It teaches something no other file in the
  archive teaches as well. Expect this to be a small minority of a real archive.
- **`redundant-of m<nnn>`** — it teaches the same thing as the named row, no better. Second copies,
  the four notebook sets that are the same course, the slide deck that restates the notes.
- **`peripheral`** — it is about something else. Adjacent topic, another project, courseware for a
  different course. Peripheral is not a quality judgment; next topic's `key` lives here.

A row's role is about **this archive**, not about the world. The registry holds the world's opinion.

## Workflow

**Input required:** Confirmed topic from `/pre-write-grill`, `frame`, or explicit author statement. 
Without topic confirmation, ask: "What specific topic or question will use this archive?" The 
confirmed topic determines which materials get deep vs light treatment.

### Step 1 — Inventory

Filename-level, recursive, junk excluded. The count is the denominator every later step is checked
against:

```bash
ARCHIVE=<archive-root>
find "$ARCHIVE" -type f \
  ! -name '.DS_Store' ! -name 'Thumbs.db' ! -name '*.tmp' ! -name 'materials.md' \
  ! -path '*/.git/*' ! -path '*/__pycache__/*' ! -path '*/.ipynb_checkpoints/*' \
  | sed "s|^$ARCHIVE/||" | sort
find "$ARCHIVE" -type f ! -name '.DS_Store' | wc -l      # the denominator
```

Report it compressed: top-level folders with counts, loose files by name. A folder holding more
than ~20 files of one kind is a bulk folder and is a candidate for a single row.

If `materials.md` already exists, read it first — this is a re-run, and Hard Rule 6 applies.

### Step 2 — Identify relevant vs peripheral materials (topic-focused)

**With confirmed topic**, categorize materials by relevance BEFORE deep reading:

- **Likely relevant** — files whose path/name/folder suggest they directly address the topic
- **Possibly relevant** — files in mixed folders or ambiguous naming
- **Likely peripheral** — files clearly about different topics or adjacent areas

This initial sort focuses deep reading effort on what matters.

### Step 3 — Read relevant materials deeply, categorize peripheral lightly

**For likely relevant materials:**
- Read **in full**: every note, every README, every link list
- **Skim** papers and notebooks to their title and first heading or first cell — enough for `kind`
  and a `concepts` line, not enough to summarize
- Write detailed `concepts` cells from actual content

**For likely peripheral materials:**
- Categorize from filename and folder structure
- Note the off-topic reason in `concepts` without deep reading
- Peripheral folders get one row with file count, not per-file rows

**For possibly relevant materials:**
- Quick inspection to confirm relevance
- Read deeply if relevant, categorize lightly if peripheral

**Do not open** images beyond their filename unless a filename is cryptic and the file sits in a
folder that is otherwise `key`. A cryptic image in a peripheral folder stays peripheral.

### Step 4 — Find the duplicates

This is the step that pays for the skill. Duplicates hide in four shapes:

| Shape | How it shows | Example |
| :--- | :--- | :--- |
| Same file twice | different filenames, same content | `Attention is All you Need.pdf` / `09 - Attention Is All You Need.pdf` |
| Same source, different medium | slides restating the notes | `12-Courseware/` vs `transformer-note.md` |
| A set from one course | N notebooks from the same lesson series | five DLAI notebook folders |
| A section restating another | inside one note | `## PE` and `## 位置编码补充` |

```bash
find "$ARCHIVE" -type f ! -name '.DS_Store' -exec shasum {} \; | sort | awk '{print $1}' | uniq -d
```

Byte-identical duplicates are free; the other three shapes need the titles. For a set, pick one
canonical `key` row and make the rest `redundant-of` it — do not make them all `key` because they
differ slightly. **Say what the redundant copies add**, if anything, in their `concepts` cell; a set
member with genuinely unique content is its own `key` row, not a redundancy.

### Step 5 — Assign roles and write the map

Work top-level folder by top-level folder. For each:

- Is the whole folder about another topic? → one `peripheral` row, `path` ending `/**`, with its
  file count and the one line saying why.
- Otherwise, row its files (or its note sections), assign `key` or `redundant-of`, and write
  `concepts` from what you actually read.

Then resolve `source-id`: for each row, look for its source in `sources/<domain>.md`. A file that
belongs to a registered source gets that `id`. A file that belongs to an *unregistered* source is
left at `—` and named in the report — that list is `/curate-sources`'s input, and this skill does
not append to the registry.

Write `materials.md` with the header counts and the rows.

### Step 6 — Write the survey stub and prove the folder is untouched

Learning skills find the archive through one line, so that no skill hard-codes a path:

```markdown
<!-- learning/<slug>/survey.md -->
# Survey: <topic>

archive: /absolute/path/to/<archive-root>
```

If `learning/<slug>/survey.md` already exists, insert or update the `archive:` line only and change
nothing else — `/survey` owns the rest of that file.

Then assert the read-only rule:

```bash
find "$ARCHIVE" -newer "$ARCHIVE/<a-file-that-predates-this-session>" -type f \
  ! -name 'materials.md' ! -name '.DS_Store'          # expect empty
```

### Step 7 — Report

- Rows written against the file denominator, and the residue if any.
- key / redundant / peripheral counts.
- The duplicate sets found, one line each — this is the finding the author will want to argue with.
- Rows whose `source-id` is `—` because the source is not in the registry → `/curate-sources <domain>`.
- Peripheral folders named, with counts: what a future topic inherits.

## Contract test

Given a 12-file synthetic fixture containing one duplicate pair and one off-topic folder: every
file is covered by a row or an ancestor folder row (rows + folder-row counts equal the denominator);
the duplicate's second copy is `redundant-of` the first and names its id; the off-topic folder is a
single `peripheral` row with `/**` and a file count, not one row per file; every `key` row's
`concepts` cell is non-empty and every `used-in` cell is `—`; `materials.md` carries the header
counts; `learning/<slug>/survey.md` exists with an `archive:` line; the fixture is byte-for-byte
unchanged apart from `materials.md` (`find -newer` returns nothing else). A second run on the same
fixture adds no duplicate ids, preserves every existing id, and leaves `used-in` untouched.

## Handoffs

**In:** Confirmed topic from `/pre-write-grill`, `frame`, or explicit author statement; a raw materials folder (the archive root for one topic); and `sources/<domain>.md` if it exists — the map resolves `source-id` against it but never writes it.

**Out:**
- `materials.md` written → `/survey` scopes from it, `/curriculum` draws lesson material from `key`
  rows only, `frame` selects `m<nnn>` ids instead of scanning cold.
- `archive:` line in `survey.md` → every learning skill locates the archive through it.
- Rows with no `source-id` → `/curate-sources <domain>` registers the sources behind them.
- The folder needs a different tree, not metadata → `/organize-docs`, as a separate decision.

**Workflow ordering:** Runs AFTER topic confirmation (via `/pre-write-grill` or direct framing), not before.

## Boundaries

- vs `frame`: this ranks the archive once for everyone; frame dispositions it per piece
  (`core`/`support`/`cut`/`gap`). Frame's rows point at this map's `m<nnn>` ids and may not select
  a `redundant-of` or `peripheral` row.
- vs `archive-materials`: that runs **after** a piece ships and fills `used-in`. This runs **before**
  learning starts and fills everything else. Same file, two owners, disjoint columns.
- vs `/curate-sources`: that ranks sources across topics in `sources/<domain>.md`; this ranks files
  within one archive. A `source-id` is the join between them.
- vs `/organize-docs`: that moves files into a MECE tree. This writes one metadata file and moves
  nothing.
- vs `clean-notes`: that rewrites the inside of one note. This never edits a note's content.
