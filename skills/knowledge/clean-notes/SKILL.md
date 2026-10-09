---
name: clean-notes
description: "Stage 1 of the knowledge pipeline: turn materials.md plus the read-only archive into MECE evidence notes under notes/ — topic understanding across all files, an outline derived from the material and confirmed with you before anything is written, duplicate and near-duplicate blocks merged, recurring angles kept, provenance ids carried through, and image paths repaired. A note merges many sources and is evidence: nothing is added, improved or judged. Use for 'clean up these notes', '整理笔记', 'dedupe this dump', 'restructure these materials by topic', or after map-materials has inventoried an archive. Does NOT write wiki pages or split a concept into pages (llm-wiki-ingest), inventory the archive (map-materials), add unmarked knowledge, write into the archive, or touch learner state."
license: MIT
metadata:
  hermes:
    tags: [knowledge-base, notes, mece, provenance]
    category: knowledge
    related_skills: [map-materials, llm-wiki-ingest, llm-wiki-lint]
---

Last updated: 2026-10-09

# Clean Notes

Stage 1 of the pipeline in [docs/knowledge-model.md](https://github.com/XinheLIU/Agentic-Knowledge-Bank/blob/main/docs/knowledge-model.md):
`materials.md` **plus the read-only archive** in, `notes/<topic>.md` out. Raw material does not
just repeat itself — it repeats itself *far apart*, so the repetition never sits next to itself long
enough to be seen. Read the material as a whole, derive its topics, cluster by topic, then dedupe; a
duplicate that was invisible three files away becomes obvious once its twin is next to it.

**Announce at start:** "I'm using the clean-notes skill to turn `materials.md` and the archive into MECE evidence notes under `notes/`."

**When to run:** after `map-materials` has written `materials.md`; before `llm-wiki-ingest` reads
`notes/`. Run once per material set. `map-materials` decides what a material *is*; this skill decides
what a note *contains*; ingest decides what a page *explains*.

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
| `$KB_PATH` | **Required, explicit, never a default.** The instance root. Holds `materials.md`; receives `notes/`. |
| `materials.md` | **Required.** The stage-0 inventory. Its header carries `archive: <abs-path>` — the only source of the archive root. |
| Topic | **Required.** The domain the instance covers. If absent, ask once. |
| Archive | Read from `materials.md`'s `archive:` line. **Read-only** — see Hard Rule 1. |

If `$KB_PATH/materials.md` is missing, stop and run `map-materials` first. Never re-derive rows the
map already holds.

## Hard Rules

1. **Never write into the archive.** Nothing here — no note, no rewrite, no image copy, no
   `.DS_Store` sweep. All writes go to `$KB_PATH/notes/`. The archive has exactly one identity: the
   read-only folder named by `materials.md`'s `archive:` line.
2. **A note merges many sources; it is evidence.** One `notes/<topic>.md` holds everything the
   material says about that topic, from any number of files and genres. A note reports what the
   material says: nothing is added, improved or judged.
3. **Provenance survives every merge.** A block may be moved or merged **only when you can name the
   block it joins or duplicates**, and only when the note keeps which `mat:` rows the merged content
   came from. If the rows cannot be named, the block stays where it is.
4. **Derive the axis; keep it shallow; one catch-all.** The topic partition comes from the content,
   never from a fixed taxonomy or the files' own folder tree. Two levels at most — note → `##`
   section. Exactly one `notes/misc.md` catch-all.
5. **Gate before writing.** Show the MECE outline and wait for the answer. Nothing is written before
   it (Step 3).
6. **Supplement only as marked `ext:`.** Only for a fact the note is unreadable without, only from a
   source fetched and verified at run time, always visibly distinct, and **never** written into
   `sources.md` — that registry is `llm-wiki-ingest`'s (Step 5).
7. **Never translate, never add knowledge, never "improve" a claim's meaning.** Compress wording only
   when merging. A heading that contradicts its own body gets a `> note:` flag, not a silent
   correction.
8. **Subagents clean; they never write files.** An inline mapping step hands each confirmed topic to
   a subagent; the subagent returns markdown, the parent writes the note.
9. **A re-run rewrites only what changed.** Unchanged notes are skipped and named in the report.
10. **Bump the note's `updated:` frontmatter field and near-top `Last updated:` date** on every
    note you write.

## The note set — MECE

A note is the **unit of topic**: `notes/<topic>.md`. The top-level topics of the outline are the
notes; a sub-topic is a `##` section inside its note, never a second file. A single note therefore
merges content from one or from many archive files — and the Transformer archive (one CN note
spanning everything, two English lesson series in shorthand) is exactly the case where one topic's
content arrives from three genres and has never been read side by side.

- **Derive, don't impose.** Read enough to know the domain, then choose **one** primary axis for
  the partition. For evidence notes the axis is almost always **by topic** (subject matter). The
  files' existing headings and folders are not the structure — two signals they are wrong: the same
  topic recurs under more than one heading or file, or one heading holds three or more unrelated
  topics.
- **Keep it shallow.** Two levels: the note, then `##` sections. A reader who cannot find a topic
  from the note list is looking at the wrong axis, not a deep-enough tree.
- **MECE.** Every block has exactly one obvious home. A block that fits two notes means the axis is
  wrong or two notes overlap — fix the axis; never file the same content twice.
- **Reserve one catch-all.** `notes/misc.md` for genuine one-offs. **If it grows past ~15% of the
  material, a topic is missing** — re-outline at the gate rather than letting `misc` become a topic.
- **The count is what the material supports.** For the Transformer archive that is on the order of
  **5–8 notes**; the exact set is fixed at the gate, and exceeding a handful is the same
  over-splitting signal the wiki layer checks.
- **`notes/` is the read-only evidence layer.** Once written, a note is read by later stages and
  never edited to suit them. One note feeds **one to several** concept pages; a page may cite
  paragraphs from more than one note. The mapping is **never** the reverse — a page never dictates
  that a note be split.

## The note template

This is this skill's convention for `notes/<topic>.md`:

````markdown
---
title: <topic>
materials: [mat:m007, mat:m012, mat:m031]   # the union of every mat: row merged into this note
updated: YYYY-MM-DD
---
# <topic>

Last updated: YYYY-MM-DD

## <sub-topic>
<cleaned, deduplicated evidence — the material's claims, in the material's order> [^mat:m007][^mat:m012]

## <sub-topic>
…

## Supplementation (ext:)      # only when used; otherwise omitted
- `ext:vaswani-2017` — <the one fact it supplies> · <url> · <version> · <fetched_at> · <sha256>

## Links from material           # only when a link or image was rewritten; otherwise omitted
- `../../images/foo.png` → `/abs/archive/images/foo.png`
- `../../../../images/bar.png` → **broken-link:** not found under the archive

## References
[^mat:m007]: `transformer-note.md § Self Attention`
[^mat:m012]: `Shrijeeth/03-attention.md`
````

`materials:` and the footnote ids are a **two-way index**: every `mat:` footnote id used appears in
`materials:`, and every entry in `materials:` is used by at least one footnote — the note-level
mirror of the page's `sources:` check.

## Steps

### 1 — Orient and prescan

Read `materials.md` in full. It already holds what each material is (`kind`) and how much attention
it deserves (`role`). Work from its rows, not from a fresh directory walk:

- **`key` rows** are the material this note set is built from.
- **`redundant-of m<nnn>` rows** are represented by the canonical row they name — do not let the copy
  create a duplicate text block. Read the copy only for content the canonical row lacks (typically
  asset references such as image links, which Step 7 re-paths).
- **`peripheral` rows** are read only when a note genuinely needs them; their topic is a different
  instance's `key`.
- **`off-topic` rows** are excluded — they were the stage-0 gate's subject. Never read them.
- **A row's `sha256`** is the drift anchor: if a re-run finds it changed, that material is re-read.

Then the mechanical prescan — literal duplicate lines anywhere in the material, regardless of where
they sit. Resolve the archive root from the map's own header once:

```bash
KB="$KB_PATH"
ARCHIVE="$(sed -n 's/^archive: //p' "$KB/materials.md")"   # the only source of the archive root
```

```bash
# LC_ALL=C is required: under a UTF-8 locale, distinct CJK lines collate as
# equal and uniq reports false duplicates — which this skill would then delete.
# Read-only scan of the whole archive; discard hits from off-topic or redundant rows.
find "$ARCHIVE" -name '*.md' -print0 | xargs -0 awk 'length($0) > 20' \
  | sed 's/^[[:space:]*•-]*//; s/[[:space:]]*$//' \
  | LC_ALL=C sort | LC_ALL=C uniq -d
```

The prescan catches literal lines only; near-duplicates in different words will not appear until
their blocks sit next to each other — that is what the topic map is for, not the prescan.

*Done when:* every `key` row has been read to the depth its role needs, and the prescan output is
recorded.

### 2 — Map topics across the whole material set

**Inline, never delegated.** List what is actually here: for each distinct topic, which blocks hold
it, in which files, and where. This step needs the whole material set — a subagent holding only one
file cannot know the topic recurs in another genre, which is the entire reason stage 1 exists.

For each candidate topic record: label, one-line definition, the `mat:` rows (or their paths and
headings) that carry it, and a rough block count. Mark a candidate `misc` only after it has survived
the map.

Split a mixed-topic paragraph or long list into coherent claim blocks before assignment; keep
qualifications, examples and citations attached. Each retained block has exactly one topic home.
A `mat:` row may feed several notes; record row + source heading/block locator → destination
note + section. Do not rewrite stage-0 rows to force topic exclusivity.

*Done when:* every retained block has one candidate home (including genuine one-offs in `misc`),
and every kept row has an explicit disposition and all its block destinations.

### 3 — Gate: propose the MECE outline, then stop

Before writing anything, show one consolidated outline and wait for the answer:

1. The **note list** — each `notes/<topic>.md` with a one-line definition and its source count.
2. Each note's **`##` sub-headings**.
3. The **duplicate clusters** found, each classified (Step 4) — the table worth arguing with.
4. Any proposed **`ext:` supplementation**: the missing fact, its topic, the candidate source.
5. The **link/image re-path plan** in one line (Step 7), including the known-broken targets.

State the chosen axis. Ask: *"Does this axis and note set work, or should it be structured
differently?"* A wrong axis is cheap to fix now and expensive after the notes exist.

On a **re-run**, gate only the notes whose source set or outline changed; name the unchanged notes
as skipped. Nothing is written before this gate.

*Done when:* the user has confirmed or amended the axis, the note set and the supplement plan.

### 4 — Cluster, then dedupe

With same-topic blocks adjacent, classify what remains:

| Kind | Test | Action |
| :--- | :--- | :--- |
| Verbatim | same wording | keep one |
| Near-duplicate | same claim, different wording or depth | merge into the fuller version, absorbing what is unique to the other |
| Recurrence | same concept, new angle, example, or number | **not a duplicate** — keep both, now adjacent under the topic they share |

**Recurrence is not duplication.** Treating recurrence as duplication is how this skill loses
content: a source that returns to one idea from four angles usually means four angles, not four
copies. Each kept block carries its own `mat:` footnote — a merged block names **every** row it came
from (Hard Rule 3).

For every merge record source row + block locator → actual retained note/section/block, repeated
claims removed, and unique qualifications/examples absorbed. A same-topic heading without those
claims is not a valid target. Compare summaries with detailed passages too; a literal-line scan or
merge count does not establish semantic deduplication. If claim preservation cannot be shown,
retain both with the unresolved overlap named rather than claiming a completed merge.

*Done when:* each duplicate cluster is resolved or explicitly unresolved, every surviving block
names its source row(s), and the merge ledger demonstrates absorption into the named target.

### 5 — Supplement, only as marked `ext:`

A note is evidence, so supplementation is the exception. Add content from outside the material **only
when the note is unreadable without it** — a term used but never defined, a formula only named, an
origin claim with no material behind it — and **never** to improve, expand or add colour. When the
threshold is met:

1. Find and **verify** the source: a real URL, the exact version read, `fetched_at`, and a `sha256`
   of the body actually read. Unverifiable → no supplement; leave the material's own words and, if
   the omission matters, say so as a `> note:`.
2. Include it in the **gate** (Step 3) as *topic + missing fact + candidate source*.
3. Write it **inline and visibly distinct** from material-derived text:

   `> **ext:vaswani-2017** — <one sentence completing the material>`

   and carry its verification data in the note's `## Supplementation (ext:)` block.
4. **Never write `sources.md`.** `llm-wiki-ingest` (2b) verifies these provisional candidates before
   registration (or reuses an existing verified work/version row). A provisional note id is not
   yet a usable page citation; lint checks registered page citations. One writer per artifact.

*Done when:* every supplement is gate-approved, inline-marked, and present in the note's
`Supplementation (ext:)` block.

### 6 — Clean

Fix typos, broken headings, heading levels, list markers, spacing. Drop transcript filler ("嗯", "so
yeah", false starts). Keep terminology, examples, punctuation (including CJK quotes), and the source's
language mix exactly as they are. A heading that contradicts its own body gets a `> note:` flag, not a
silent correction.

*Done when:* the note reads as clean evidence and no claim's meaning has changed.

### 7 — Repair image paths and links

A note lives in `$KB_PATH/notes/`; the material it came from lives elsewhere, so an inherited
relative link (`../../../../images/foo.png`) is wrong by construction. Rewrite each inherited
**local asset link** as an absolute archive path, computed from the source file's directory and
`archive:` root. Percent-encode spaces/reserved path characters, or wrap the destination in `<...>`:
`![alt](/abs/archive/image%20name.png)` or `![alt](</abs/archive/image name.png>)`.
Preserve alt text and provenance exactly. Keep valid external URLs and document anchors as such.
Decode existing percent escapes once for filesystem resolution; do not double-encode them.

- **Resolvable target** → the absolute archive path.
- **Known-broken target** (flagged `broken-link` in `materials.md`, e.g. the 34 `../../../../images`
  paths) → search the archive for the real target (commonly the same basename under the archive's
  `images/`). Found → the absolute path. Not found → a literal
  `> **broken-link:** <original>` marker, kept in the note; never silently dropped.
- Record `original → rewritten` for every change in the note's `## Links from material` block, so
  the rewrite is auditable.

Never copy an image out of the archive. If the archive moves, report the mismatch; absolute links
need stage-owned repair as well as an updated inventory header.

*Done when:* every inherited local asset link either renders and resolves to an absolute archive
path or has an explicit `broken-link` marker; every rewrite appears in the ledger. Render the
Markdown with a CommonMark/GFM renderer: each intended image must become an `<img>` with non-empty
alt and a decoded `src` pointing to an existing, non-zero image verified by magic bytes (SVG by
markup). File existence alone is not completion. Use lint's L4 asset checker or an equivalent
renderer-backed check and report every failure; external bytes remain unverified without fetching.

### 8 — Write and report

Write each `notes/<topic>.md` from the confirmed outline. Report in chat:

- The outline actually used and the axis chosen; how many notes were produced.
- The **full per-row assignment table** — every `mat:` row, all target notes/sections, its action and block locators.
- Duplicates removed by kind; recurrences kept.
- Images re-pathed and links left broken; anything marked `ext:`.
- The 15% check on `notes/misc.md`.

Nothing about the cleaning is persisted except the notes themselves.

*Done when:* every note in the confirmed outline exists, every `mat:` footnote id resolves to a
`materials.md` row and every provisional supplement carries its handoff metadata, and the report is complete.

## Input size

Mapping is always inline; only the writing fans out. A subagent seeing one file cannot know its
topic recurs elsewhere, so Step 2 runs first, and any split follows the **confirmed outline**, never
the source files' original headings.

| Material set | Path |
| :--- | :--- |
| One short file, or a few short files totalling ≲500 lines | Steps 1–8 in one pass, inline. |
| The parent has already read every source in full during the mandatory inline Step 2 map | Steps 4–8 inline, one pass after the gate. The fan-out exists for context isolation, not labour-saving — when the parent already holds the whole set, dispatching subagents adds verbatim-fidelity risk with no benefit. |
| The normal case — many files, several genres, roughly 500–3000 lines | Steps 1–3 inline (map + gate); then **one subagent per confirmed note**. Each gets every block assigned to its topic, from any file, plus those rows' `mat:` ids, and returns cleaned, deduplicated, image-repaired markdown for that note only (Steps 4–7 for its topic). Concatenate in outline order and write (Step 8). Subagents clean; they never write files. |
| ≳3000 lines, or a set containing one unmanageable monolith | If one file is the monolith, split it into `notes/.parts/` first, build a lightweight per-part topic list, merge the part lists by shared topic label into one outline, confirm it, then run the per-note fan-out above. Never attempt a single pass over the monolith. |

## Guardrails

- The archive is read-only; `notes/` is written. Ask before dropping anything that is not a
  duplicate.
- Never translate, never add unmarked knowledge, never "improve" a claim's meaning — compress
  wording only when merging.
- A block moves or merges only when you can name the block it joins or duplicates.
- Already clustered and clean → say so and stop. Do not reorganize a note set to look busy.
- A note is evidence, not prose: do not craft an argument or a narrative thread — that is
  `llm-wiki-ingest`'s job.
- Navigation-only boilerplate (a lesson index linking sibling files, a course outline) is neither
  evidence nor a broken link. Drop it and say so in the report; never keep it as a claim.
- A `key` folder row's files that no material links to have no reference to re-path and are not
  reachable from the notes. Record that in the report; never invent a link to reach them.
- Bump the note's `updated:` frontmatter field on every note you write.

## Handoffs

**In:** `$KB_PATH` + `materials.md` + the topic. Nothing else — this skill reads no other product's
file.

**Out:** `$KB_PATH/notes/<topic>.md` → `llm-wiki-ingest`, which proposes the narrative and writes
concept pages from them. One note feeds one to several pages; a page may cite several notes. The
mapping is never reversed.

**Boundaries:**
- vs `map-materials`: that decides what each material is and flags it; this reads those rows and
  never re-inventories the archive.
- vs `llm-wiki-ingest`: that writes the presentation layer (`wiki/`, `narrative.md`, `sources.md`,
  `SCHEMA.md`, `index.md`, `log.md`); this writes the evidence layer (`notes/`) and never writes a
  wiki page, a narrative, or a source registry row.
- vs `llm-wiki-lint`: that audits pages and asset links in both layers read-only; it does not certify notes'
  semantic fidelity or deduplication. This is where notes are made.
- Learner state (attempts, mastery) belongs to Learning OS and is never read or written here.
