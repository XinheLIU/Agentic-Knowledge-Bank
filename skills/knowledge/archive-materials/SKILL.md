---
name: archive-materials
description: "After a piece is delivered, record actual material use and source verdicts in the material map and source registry. Use for 素材归档 or library usage feedback; writing judgments and topic connections belong to snapshot-writing."
---

Last updated: 2026-10-04

# Archive Materials

## Overview

A shipped piece in, **evidence out** — into the two files that decide what the next topic reads:

| Write | Into | Says |
| :--- | :--- | :--- |
| `used-in` cells | `<archive>/materials.md` | which materials the chapter actually used, and where |
| verdicts | `sources/<domain>.md` | which registry sources held up in real use |
| confirmed renames | the archive | cryptic filenames, fixed in one batch |

**This is the material-library usage write-back.** Writing judgments and topic relationships are
recorded separately by `snapshot-writing`; this skill never writes writing memory. `/map-materials` ranks an archive on a guess about what
will be useful and `/curate-sources` tiers sources on reputation; both are hypotheses. A shipped
chapter is the first evidence either one has ever seen. Without this skill the tiers never move,
the map is a one-time opinion, and every topic starts from the same guess — the "continuously
updated registry" is just a registry.

**Evidence, therefore last.** Sorting a folder before knowing what will be written is guesswork
about a future chapter; recording it after a chapter shipped is bookkeeping against fact. The
library also outlives the piece: the folders this chapter cut are the next chapter's `key`.

Everything written is additive. Nothing is deleted, nothing moves between folders, no tree is
reshaped, and no `tier` cell is touched. Those are `organize-docs` and `/curate-sources`, and they
are different decisions made by different skills.

## Hard Rules

1. **Never delete. Never move across folders. Never restructure.** Including files that look like
   junk, duplicates, and `12-Courseware`. Point them out; don't act.
2. **Additive writes only** — `used-in` cells in `materials.md`, verdict lines in
   `sources/<domain>.md`, plus renames the author confirmed. Nothing else, anywhere.
   Specifically: never a `role` cell (that is `/map-materials`), never a `tier` cell (that is
   `/curate-sources`), never a new material row unless the file arrived after the map was written.
3. **Renames are confirmed in one batch, never applied file by file as you think of them.** Show
   the full old → new list; apply only on an explicit yes.
4. **Check for inbound references before any rename.** A note that embeds `images/Foo.png` breaks
   when `Foo.png` is renamed. Grep the folder first; if a reference exists, either update it in the
   same batch and say so, or drop the rename. Never leave a dangling reference behind.
5. **Every material file is covered by a row** — its own, or an ancestor folder's (`06-Vision/**`).
   The map already guarantees this; your job is to notice files that arrived since, and add rows
   for those only.
6. **`used-in` is evidence, not intent.** A row gets one only if the shipped draft actually used
   that file. A `core` disposition in the brief that never reached the draft is recorded as
   `planned, unused` — that gap is the most useful thing the manifest records.
7. **Re-runs append.** A second chapter from the same library adds `used-in` pointers and new rows;
   it never rewrites another piece's rows or resets a caption the author edited.
8. **Never judge the material in the map.** No "low quality", no "superseded by" in a `materials.md`
   cell. Usage is a fact; quality is a verdict, and verdicts go in the registry with a pointer.
9. **A verdict needs a pointer into the shipped piece.** `<piece> § <section>`. "Was useful" is not
   a verdict.

## Workflow

### Step 1: Read the evidence

Four inputs, in this order:

- `drafts/<piece>/brief.md` — the selection map: what the piece *planned* to use. Read v2 `Nodes` or legacy `支撑节点`; preserve `m<nnn>` IDs when a material map exists. Evidence rows give precise source passages; a selected row alone is not proof of actual use.
- The shipped draft — grep it for what actually landed. Dispositions are claims; the draft is fact.
- `<archive>/materials.md` — the map, found via the `archive:` line in `learning/<slug>/survey.md`.
- `sources/<domain>.md` — the registry, for the `source-id` behind each used material.

```bash
ARCHIVE=$(sed -n 's/^archive: //p' learning/<slug>/survey.md)
PIECE=<draft-folder>

find "$ARCHIVE" -type f ! -name '.DS_Store' ! -name 'materials.md' | sed "s|^$ARCHIVE/||" | sort
grep -oE '!\[[^]]*\]\([^)]+\)' "$PIECE"/<chapter>.md | sort -u      # images actually placed
grep -oE 'm[0-9]{3}' "$PIECE"/brief.md | sort -u                       # materials the brief selected
```

Draft assets are **copies** under `drafts/<piece>/assets/`, so map them back to their map rows by
filename. Say out loud when a copy's name no longer matches any original — the image was renamed or
regenerated during drafting, and the pointer needs the author.

Files in the archive with no map row arrived after the map was written: add rows for those (id,
path, kind, `source-id`, `role`, `concepts`) and say so. That is the only new-row case.

### Step 2: Fill `used-in`

For every map row the shipped draft actually used, write `<piece> § <section>` into its `used-in`
cell. Three values and nothing else:

| `used-in` | When |
| :--- | :--- |
| `<piece> § <section>` | the draft used it. Multiple sections: comma-separate |
| `planned, unused` | the brief selected it `core`/`support` and the draft never used it |
| `—` | the brief never selected it |

**`used-in` is evidence, not intent.** The `planned, unused` marker is the most useful thing this
step records: it is the gap between what the author thought they needed and what the chapter
turned out to need, and it is the input to the next map's `role` calls.

A re-run for a second piece **appends** to the cell (`transformer § 1.7, attention-2 § 3`); it
never rewrites another piece's pointer.

### Step 3: Write the registry verdicts

For every registry source the chapter leaned on — found by following the used rows' `source-id`
column — append one line to `sources/<domain>.md` under `## Verdicts`, per
[`sources/README.md`](../../../../information-assistant/docs/source-registry.md#verdict-format):

```text
#v14 2026-10-12 vaswani-attention hold drafts/transformer/transformer.md § 1.3 — §3.2 carried the
  whole √d_k section; nothing else in the archive makes that argument.
#v15 2026-10-12 d2l-attention promote drafts/transformer/transformer.md § 2.1 — the block-anatomy
  figure is what made the residual path explicable; better than its tier-2 standing suggested.
```

Rules:

- **`hold` or `promote` only.** A chapter that used a source is evidence it was usable. `demote`
  comes from error clusters, and that is `/reflect`'s verdict to write.
- **One verdict per source**, not one per section.
- **Never edit a `tier` cell.** `/curate-sources` applies these on its next run — the skill that
  changes a tier is the one that reads the whole registry.
- A source with `planned, unused` material and nothing used gets **no verdict**: a source the
  chapter did not use tells you nothing about the source.

### Step 4: Offer renames

Cryptic filenames are the library's real debt. Propose a batch — old → new, plus the inbound-
reference check from Hard Rule 4 — and apply only on confirm.

Naming rule: describe the content, keep the existing convention of the folder, don't renumber
anything. `Classic Encoder-Decoder Transformer 2.png` → `Encoder-Decoder-Data-Flow.png` is a good
rename; renumbering `01-Foundations/` is a restructure and out of bounds.

A rename changes a `path` cell in `materials.md`, so update it in the same batch — a map pointing
at a filename that no longer exists is worse than a cryptic filename.

After applying, verify nothing downstream broke using the shared reference checker:

```bash
python3 <writing-assistant>/skills/writing/scripts/verify_references.py "$PIECE"/<chapter>.md
grep -rn '<old-filename>' "$ARCHIVE" --include='*.md'      # expect no output
```

The shipped chapter is safe by construction — its assets are copies — but run the check anyway: it
is the assertion that the copy discipline actually held.

### Step 5: Offer `clean-notes`

For note files worth keeping as standalone notes — not because the chapter used them, but because
the author will reread them — offer `/clean-notes`. One file in, one file out; it is a separate
decision per file and it is fine for the answer to be no. Never run it unasked: the chapter is
already written, so cleaning now serves the library, and that is the author's call.

### Step 6: Report

- `used-in` cells filled, against the map's row count.
- `planned, unused` count and the rows: material the brief promised and the draft never used.
- Verdicts appended, one line each, and the note that `/curate-sources` applies them next.
- New rows added for files that post-date the map.
- Renames applied, and the reference check result.
- What the next chapter inherits: the `peripheral` folders, named, with their file counts.

## Contract test

Every material the shipped draft used has a `used-in` cell naming the piece and section; every
`core`/`support` row of the brief that the draft never used is marked `planned, unused`; every
other row stays `—`. Every registry source behind a used material gets exactly one `hold` or
`promote` verdict carrying a pointer into the shipped draft, and **no `tier` cell is written**; a
source with only `planned, unused` material gets no verdict; a `demote` written here is rejected.
No `role`, `concepts`, or `id` cell is changed, and new rows appear only for files that post-date
the map. Renames update their `path` cells in the same batch, leave the shipped chapter's
references intact (`verify_references.py` reports zero BROKEN), and leave no dangling intra-folder
reference. Nothing is deleted and nothing moves between folders. A second run for a second piece
appends to `used-in` rather than rewriting the first piece's pointer, and appends verdicts rather
than editing existing ones. Only `materials.md`, `sources/<domain>.md`, and confirmed renames are
written.

## Handoffs

**In:** a shipped piece — `drafts/<piece>/brief.md` plus the final draft (normally after
`package-chapter`) — the archive it was written from with its `materials.md`, and
`sources/<domain>.md`.

**Out:**
- `used-in` filled → the next `/map-materials` re-run and the next `frame` see what a real chapter
  actually needed, not what someone guessed.
- Verdicts appended → `/curate-sources` applies them to tiers on its next run → the next `/survey`
  scopes against a registry that learned something.
- `planned, unused` rows → the gap between the brief and the draft → useful to `frame` next time.
- Notes worth keeping → `/clean-notes`, one file at a time.
- The folder genuinely needs a new tree, not metadata → `/organize-docs`, as a separate, explicit
  decision.

## Boundaries

- vs `organize-docs`: that restructures a folder into a MECE tree and moves files. This adds two
  metadata files and renames in place. If the answer is "this folder needs a different shape", stop
  and say so — don't half-do it here.
- vs `clean-notes`: that rewrites the inside of one note. This offers it and records the outcome.
- vs `frame` / `develop-examples`: those plan and select before writing and never write to the archive. This records after
  shipping, and is the only skill in the loop that writes there.
- vs the `raw/` promotion rule: a materials library is not a `raw/` layer — it is a curated folder
  the author maintains, and the manifests are the curation.
