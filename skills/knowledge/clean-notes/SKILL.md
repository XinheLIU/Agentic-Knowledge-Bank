---
name: clean-notes
description: |
  Clean one raw capture — video transcript, AI-generated summary, lecture dump,
  scraped article, messy personal notes — into readable, topic-clustered notes:
  similar content grouped so repetition becomes visible, duplicates removed,
  headings and typos fixed. Confirms any real reorganization with you first,
  like an editor proposing a course-notes outline. Use for "clean up these
  notes", "dedupe this dump", "organize this transcript by topic". One file in,
  one file out. Does NOT split content into multiple chapters or wiki pages
  (llm-wiki-ingest), restructure a FOLDER of documents (organize-docs),
  translate (book-translator), or write prose (write-content).
---

Last updated: 2026-10-04

# Clean Notes

The **process** stage of the [information pipeline](../README.md): `raw/` → `notes/`. Raw captures don't just repeat themselves — they repeat themselves *far apart*, so the repetition never sits next to itself long enough to be seen. Cluster by topic first; a duplicate that was invisible three sections away becomes obvious once its twin is next to it.

**Invariant:** move or merge a block only when you can name the block it joins or duplicates. Everything else stays — claims you think are wrong, filler you find ugly, fragments that go nowhere.

**In scope:** one material's capture (one file, or several files of the same material), reorganized *inside that file* — new subheadings, blocks moved to the topic that owns them, duplicates merged. **Out of scope:** splitting into multiple files, chapters, or wiki pages (`llm-wiki-ingest`) · translating · adding knowledge the source lacks · editing `raw/`, which is immutable · turning notes into prose · judging whether the source is right.

## Steps

**1. Orient.** Read the capture. Take provenance from its header — source, date, medium; anything absent is `unknown`, never invented. Ask once if there is none at all. Pick the size path below.

**2. Map topics.** Before touching anything, list what's actually here: for each distinct topic, which blocks hold it and where. Two signals mean the current headings aren't the real structure: the same topic recurs under more than one heading, or one heading holds three or more unrelated topics. A mechanical prescan catches literal duplicate lines regardless of location, but near-duplicates in different words won't show up until their blocks sit next to each other — that's what the map is for, not the prescan.

```bash
# LC_ALL=C is required: under a UTF-8 locale, distinct CJK lines collate as
# equal and uniq reports false duplicates — which this skill would then delete.
awk 'length($0) > 20' raw/<file>.md | sed 's/^[[:space:]*•-]*//; s/[[:space:]]*$//' \
  | LC_ALL=C sort | LC_ALL=C uniq -d
```

**3. Propose the outline, confirm before moving anything.** If the map already matches the current headings, skip to step 4. Otherwise show the proposed outline — target sections and subheadings, and which current blocks move where — and confirm it before writing, the way an editor checks a restructuring plan before touching someone's notes. Keep the outline itself short: labels and block counts, not the content.

**4. Cluster, then dedupe.** Move each block under the (sub)heading that owns its topic; add a subheading inside a section only where the confirmed outline calls for it. With same-topic blocks now adjacent, classify what's left:

| Kind | Test | Action |
| :--- | :--- | :--- |
| Verbatim | same wording | keep one |
| Near-duplicate | same claim, different wording or depth | merge into the fuller version, absorbing what is unique to the other |
| Recurrence | same concept, new angle, example, or number | **not a duplicate** — keep both, now adjacent under the topic they share |

Treating recurrence as duplication is how this skill loses content: a source that returns to one idea from four angles usually means four angles, not four copies.

**5. Clean.** Fix typos, broken headings, heading levels, list markers, spacing. Drop transcript filler ("嗯", "so yeah", false starts). Keep terminology, examples, punctuation (including CJK quotes), and the source's language mix exactly as they are. A heading that contradicts its own body gets a `> note:` flag, not a silent correction.

**6. Write and report.** Write `notes/<same-slug>.md`, one output file per input file. Report in chat: the outline actually used, blocks moved, duplicates removed by kind, headings fixed, anything flagged. Nothing about the cleaning is persisted.

## Input size

Mapping needs the whole document — a subagent seeing one section can't know its topic recurs three sections away. So step 2 always runs first, and any subagent split follows the confirmed outline, not the source's original headings.

| Input | Path |
| :--- | :--- |
| ≤ ~500 lines | steps 2–6 in one pass, inline |
| ~500–3000 lines, or multi-chapter | map and confirm the outline first (inline); then one subagent per confirmed cluster — each gets its own blocks, wherever they originated, and returns cleaned, deduplicated markdown for that cluster only. Concatenate in outline order. Subagents clean; they never write files. |
| > ~3000 lines, or too long to hold at once | split by top-level heading into `notes/.parts/` first, build a lightweight per-part topic list, merge the lists by shared topic label into one outline, confirm it, then run the middle path against the confirmed clusters. Never attempt a single pass. |

## Guardrails

- `raw/` is read-only. Ask before dropping anything that is not a duplicate.
- Never translate, never add knowledge, never "improve" a claim's meaning — compress wording only when merging.
- A headingless transcript may have headings derived from its content; that is the only structural addition that doesn't need confirmation.
- Already clustered and clean → say so and stop. Do not reorganize a file to look busy.
- Update `Last updated:` on files you edit.

## Handoffs

**In:** a `raw/` capture, per the intake conventions in [the pipeline contract](../README.md).

**Out:** cleaned, clustered notes → `llm-wiki-ingest` (chapters, pages, cross-links) · `organize-docs` (once several materials' notes need one structure) · `/survey` and `/curriculum` (grounded teaching material) · `write-content` (sourced material for a draft).

**Boundaries:** `organize-docs` structures a *folder* of documents, this structures *inside one file*; `llm-wiki-ingest` splits a source into separate linked pages, this reorganizes within a single file and never produces more than one output file per input; learner evidence lives only under `learning/<slug>/` and is never written here.
