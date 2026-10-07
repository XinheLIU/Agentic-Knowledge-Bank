---
name: organize-docs
description: Organize a set of documents into a clear, MECE structure and generate an index/README that summarizes it. Use when the user asks to organize, tidy up, restructure, refactor, dedupe, or make sense of a folder of notes, research, reports, meeting notes, specs, or mixed markdown/text/PDF files. Derives categories from the content itself rather than imposing a fixed taxonomy. For a CODE REPOSITORY's docs (verify-against-code, canonical /docs software layout), use organize-codebase-docs instead.
---

Last updated: 2026-08-04

**Announce at start:** "I'm using the organize-docs skill to organize this document set into a MECE structure with a summary."

## Goal

Take a loose, messy, or flat set of documents and leave behind a structure that is **clear**, **MECE** (mutually exclusive, collectively exhaustive), and **navigable**, topped with an index/README that summarizes what is there. Apply changes only after user confirmation.

Unlike `organize-codebase-docs`, this skill does **not** assume the documents describe a software system, does **not** verify claims against source code, and does **not** impose a fixed `/docs` software taxonomy. It **derives** the category structure from the documents themselves.

**When to use the other skill instead:** If the target is a code repository and the goal is to put architecture/API/runbook docs into canonical `/docs` homes and verify them against live code, use `organize-codebase-docs`.

---

## In Scope vs Out of Scope

### In scope

- Any human-authored document set: notes, research, meeting notes, reports, essays, specs, PRDs, briefs, references, clippings, wikis, personal knowledge bases.
- Text-first formats: markdown, plain text, and (read-only) PDFs, docx, or similar the user points at.
- The folder(s) the user names, plus their subfolders.

### Out of scope

- **Do not verify against code.** This skill treats documents as the source of truth, not a codebase.
- Runtime skill/prompt/agent-package trees and their bundled materials (`references/`, `assets/`, `evals/`), unless the user explicitly says those files ARE the document set to organize.
- Vendored, generated, cache, and dependency directories (`node_modules/`, `.git/`, `.venv/`, build outputs).
- Binary assets the user did not ask to organize (images, datasets) — leave them in place and reference them, do not move.

---

## Structuring Principle: Derive, Don't Impose

There is no fixed folder model. The right structure depends on what the documents are about. Derive it:

1. **Read enough to know the domain.** Sample titles, headings, and opening lines across the set. Identify the recurring subjects.
2. **Choose ONE primary axis** for the top level. Common axes — pick the one that makes the set most navigable:
   - **By topic** (subject matter) — best for research, notes, wikis.
   - **By type** (report / meeting note / reference / draft) — best for mixed-format working sets.
   - **By project or initiative** — best when docs cluster around distinct efforts.
   - **By time** (year/quarter) — best for logs, journals, or append-only records.
   - **By lifecycle/status** (active / archived / draft) — best when staleness is the main problem.
3. **Keep it shallow.** Two levels is usually the sweet spot. Anything a reader can't find within **two clicks** from the index is too deep.
4. **Make categories MECE.** Every document has exactly one obvious home. If a doc fits two categories, the axis is wrong or the categories overlap — fix the axis, don't file it twice.
5. **Reserve a catch-all.** Add a single `misc/` or `unsorted/` folder for genuine one-offs. If it grows past ~15% of the set, a category is missing.

State the chosen axis and the resulting category list explicitly before proposing moves, so the user can redirect early.

---

## Step 1 — Inventory the Documents

1. Glob the target folder(s) for documents, excluding out-of-scope locations.
2. Record for each file: **path**, **line/word count** (or page count for PDF), **last-modified date**, **title** (first heading or filename), **one-line gist** (what it's about).
3. Present the inventory as a table:

```text
| #   | File | Size | Last Modified | Title | Gist |
| --- | ---- | ---- | ------------- | ----- | ---- |
```

For large sets (50+ files), sample and cluster rather than reading every file end to end; delegate broad reads to a sub-agent to preserve context.

---

## Step 2 — Propose the Structure

1. State the **primary axis** you chose and why (one sentence).
2. List the **top-level categories** with a one-line definition of what belongs in each. These must be MECE.
3. Present the proposed tree:

```text
proposed/
├── <category-a>/        ← <one-line definition>
├── <category-b>/        ← <one-line definition>
├── misc/                ← genuine one-offs
└── README.md            ← generated index (Step 5)
```

Ask early: **"Does this axis and category set work, or should I structure it differently?"** A wrong axis is cheap to fix now, expensive after moves.

---

## Step 3 — Assign Each Document a Home

For each file, classify as one of:

- `MOVE to <category>/`
- `KEEP IN PLACE` (already correctly located)
- `MERGE into <target>` (near-duplicate or subset of another doc)
- `SPLIT` (covers multiple categories → break into focused docs)
- `RENAME` (filename does not reflect content)
- `DELETE (obsolete/empty)` — only propose, never silent
- `MISC` (genuine one-off)

Record: **file**, **current location**, **target**, **action**, **reason**.

---

## Step 4 — Find Duplicates, Conflicts, and Stale Content

Compare documents covering the same subject. Look for:

1. **Near-duplicates** — same content in two files → merge, keep the fuller one.
2. **Subset duplication** — one doc is contained in another → fold in.
3. **Contradictory facts** across docs → flag for the user; do NOT silently pick a winner.
4. **Terminology drift** — same concept, different names → note it; normalize only if the user agrees.
5. **Stale / empty / orphaned** files → propose delete or archive.

For each: **topic**, **files involved**, **canonical home**, **what stays**, **what merges/removes**, **why**.

Never delete unique content silently. When in doubt, move to `misc/` or an `archive/` folder instead of deleting.

---

## Step 5 — Generate the Index / README

The deliverable is not just a tidy folder — it's a folder a stranger can navigate. Produce a `README.md` (or `INDEX.md`) at the root of the organized set:

```text
# <Collection Name>

Last updated: <YYYY-MM-DD>

<1–3 sentence summary of what this collection is and how it's organized.>

## Structure

- **<category-a>/** — <what's here> (<N> docs)
- **<category-b>/** — <what's here> (<N> docs)
- **misc/** — <what's here>

## Highlights

- [<Most useful/entry doc>](<path>) — <why start here>
- [<Key doc>](<path>) — <one line>
```

Scale the index to the set: a 10-file collection gets a short list; a 100-file collection gets per-category sub-indexes.

---

## Step 6 — Produce the Organization Report

```text
## Organize Docs Report

### Chosen Structure
Primary axis: <axis> — <why>
Categories: <list>

### Inventory
| #   | File | Gist | Action |
| --- | ---- | ---- | ------ |

### Assignments
| #   | File | Current | Target | Action | Reason |
| --- | ---- | ------- | ------ | ------ | ------ |

### Duplicates / Conflicts / Stale
| #   | Topic | Files | Canonical Home | Action |
| --- | ----- | ----- | -------------- | ------ |

### Proposed Actions (ordered)
1. CREATE: <category folders>
2. MOVE: <file> -> <target> — <reason>
3. MERGE: <file-a> + <file-b> -> <target>
4. SPLIT: <file> -> <targets>
5. RENAME: <file> -> <new name>
6. DELETE: <file> — <reason>
7. GENERATE: README.md index
```

Ask: **"Apply all changes? (yes / yes but skip #N,M / no)"**

---

## Step 7 — Apply Changes (on confirmation)

Execute in this order:

1. **Create the category folders.**
2. **Move files** into their homes.
3. **Merge and split** as planned.
4. **Rename** files whose names don't match content.
5. **Repair internal links** between docs that moved.
6. **Delete/archive** obsolete content (only what was confirmed).
7. **Generate the root README/index.**
8. **Update `Last updated:`** near the top of every markdown file you edited (and the new index).

Report:

**"Done. <N> files moved, <M> merged, <S> split, <D> removed. Index written to <path>."**

---

## Guardrails

- **Derive the structure from the content; do not impose a fixed taxonomy.** State the chosen axis before moving anything.
- **Keep it shallow and MECE.** Two levels, one home per doc, one catch-all folder.
- **Never delete unique content silently.** Archive or move to `misc/` when unsure.
- **Do not verify against code** — that is `organize-codebase-docs`'s job.
- **Do not move binary assets** the user didn't ask about; reference them in place.
- **Confirm the axis early and the full action list before applying.**
- **Always end with an index/README** so the reorganized set is navigable.
- **Update `Last updated:` on every markdown file you touch.**
- **When unsure about a document's home or a conflict's resolution, flag it — don't guess.**
