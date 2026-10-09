---
name: map-materials
description: "Stage 0 of the knowledge pipeline: inventory a read-only archive folder into materials.md — one row per material (a file, or a ## section of one), with a stable mat: id, sha256, and a key / redundant-of / peripheral / off-topic role, plus broken-link and nested-heading flags. Confirms off-topic exclusions with you before writing. Use for 'map these materials', '整理素材', 素材分级, 材料处理, or as the first step before cleaning notes on a topic whose archive has never been inventoried."
license: MIT
metadata:
  hermes:
    tags: [knowledge-base, inventory, provenance, materials]
    category: knowledge
    related_skills: [clean-notes, llm-wiki-ingest, llm-wiki-lint]
---

Last updated: 2026-10-09

# Map Materials

Stage 0 of the pipeline in [docs/knowledge-model.md](../../../docs/knowledge-model.md):
an external, read-only **archive** in, one inventory out — `materials.md` in the knowledge
**instance**, one row per material, saying what it is and how much of it is worth attention.

**Announce at start:** "I'm using the map-materials skill to inventory this archive into `materials.md`."

**When to run:** first, before `clean-notes`. Run once per archive. Every later stage reads a row
instead of re-deriving one, so a wrong judgment is wrong in one place, visibly, where it can be
fixed.

The map is **processing, not curation**. It says "these five notebooks are the same notebook" and
"this folder is about vision, not this topic". It does not decide what a page will use, and it does
not rate how good a source is.

## Invocation and inputs

| Input | Rule |
| :-- | :-- |
| Archive root | **Absolute path, required.** The external read-only folder. Recorded in the map's header. |
| `$KB_PATH` | **Required, explicit, never a default.** The instance root. Created if absent. |
| Topic | **Required.** The domain this instance covers. If absent, ask once: "What topic or question will use this archive?" Do not derive it from a folder name. |

Stage 0 **creates `$KB_PATH` if it does not exist and writes exactly one file: `materials.md`.**
It does not write `SCHEMA.md`, `narrative.md`, `sources.md`, `index.md` or `log.md` — the instance
schema and the registry are `llm-wiki-ingest`'s to bootstrap.

## The archive is read-only

The archive is the accumulated raw material — large, unversioned, cloud-synced, and full of files
you did not write. It is **written to zero times**: not a map, not a rename, not a hash refresh, not
a `.DS_Store` sweep. A folder that genuinely needs a different tree is a separate, explicit decision
by the author, not a side effect of mapping.

This is proved, not promised: capture an archive **manifest** before anything is written and diff it
at the end, and anchor the session with an mtime marker so no file in the archive can be newer than
the session start (Step 7). Two identical manifests, and an empty `find -newer`, mean no byte of the
archive moved.

## Hard Rules

1. **Never write into the archive.** Prove it at the end with the manifest diff and the
   `find -newer` assertion (Step 7). The only file this skill writes is `$KB_PATH/materials.md`.
2. **Every file is covered by a row** — its own, or an ancestor folder's. A file nobody rowed is the
   one that turns up unexplained in three months.
3. **A duplicate is `redundant-of <id>`, never deleted and never omitted.** Name the canonical row.
   Prefer the better filename, then the better-named folder. A redundant copy may still be the *only*
   carrier of a unique asset reference (an image link, a notebook path) — the role stays
   `redundant-of`, and the `concepts` cell says what the copy uniquely carries.
4. **`concepts` comes from the file's content, never from its filename** — for every `key` row. A
   `peripheral`, `off-topic` or `redundant-of` row may be described from its filename and folder,
   because nothing downstream will teach from it.
5. **Never fill `used-in`.** That column is evidence about a shipped piece, owned by
   `archive-materials` (Writing Assistant). At mapping time every cell is `—`, and a re-run leaves
   it byte-identical.
6. **A re-run appends and refreshes; it never rewrites.** New files get new ids; existing rows keep
   their id, their `used-in`, and any `concepts` the author edited. Ids are never reused. A file
   that disappeared keeps its row and gains the `missing` flag — rows are never silently deleted.
7. **A row's `path` is relative to the archive root.** A section row is `file.md § Heading`. A folder
   row ends in `/**` and carries its file count in `concepts`.
8. **A folder gets one row, not one per file** — with its file count and the one line saying why the
   whole folder shares the fate. **A loose file keeps its own row**, and a scattered exception inside
   a mixed folder (one off-topic image among 120 on-topic ones) gets its own row too. The rule is
   against exploding a *whole* folder, not against the role. When a folder is mixed this way, the
   ancestor row covers the **remainder** — its subtree minus the exception rows — and its file count
   and manifest digest cover exactly that remainder, not the whole folder.
9. **A long note is rowed per `##` section when its sections have different fates.** One section row
   per `##`, sharing the file's `sha256`; a short single-topic lesson is one row.
10. **Say what you could not open.** A binary you did not read, a PDF you only took the title from —
    the row says so. A guessed `concepts` cell is worse than an empty one.
11. **Confirm the off-topic exclusions before writing** (Step 6). That list is the gate.

## The map

`$KB_PATH/materials.md`:

````markdown
# Materials — <topic>

Last updated: YYYY-MM-DD
archive: /absolute/path/to/<archive-root>

Mapped by `/map-materials`. Rows are appended, never rewritten. `used-in` is filled by
`/archive-materials` after a piece ships.

Files: <n> · key <n> · redundant <n> · peripheral <n> · off-topic <n>

| id | path | kind | role | sha256 | concepts | flags | used-in |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| m001 | `transformer-note.md § Self Attention` | note | key | <hex> | QKV 三个投影的分工;打分—softmax—加权求和 | — | — |
| m002 | `03-Core-Papers/Attention is All you Need.pdf` | paper | key | <hex> | 原始架构;§3.2 scaled dot-product 与 √d_k 的论证 | — | — |
| m003 | `03-Core-Papers/09 - Attention Is All You Need.pdf` | paper | redundant-of m002 | <hex> | same paper, second copy | — | — |
| m004 | `06-Vision/**` (10) | paper | peripheral | <mdigest> | ViT and the vision branch — a different topic's chapter | — | — |
| m005 | `images/Claude API 503 Error.png` | image | off-topic | <hex> | a tool error screenshot, not Transformer material | — | — |
````

### Columns

| Column | Rule |
| :-- | :-- |
| `id` | `m<nnn>`, unique within this map, **stable forever, never reused** |
| `path` | relative to the archive root. A note is rowed per section (`file.md § Heading`) when its sections have different fates; a folder row ends in `/**` and carries its file count in `concepts` |
| `kind` | `note` \| `paper` \| `notebook` \| `code` \| `image` \| `slides` \| `link-list` \| `data` \| `other` |
| `role` | `key` \| `redundant-of m<nnn>` \| `peripheral` \| `off-topic` |
| `sha256` | hash of the file as read; a section row takes its file's hash; a folder row carries a **manifest digest** of its covered files (the remainder — Hard Rule 8) |
| `concepts` | what this material actually teaches, in one line; for a folder row, its file count plus why the folder shares a fate |
| `flags` | `broken-link` \| `nested-heading` \| `unreadable` \| `missing` \| `—` (comma-separate; `—` when clean) |
| `used-in` | `<piece> § <section>`, or `—`. **Never written here** — owned by `archive-materials` (Writing Assistant) |

`source-id` is **not** a stage-0 column. The cross-topic registry belongs to Information Assistant;
when that product first supplies the join, its owner adds the column once and fills every row
(match by `mat:` id). See `docs/knowledge-model.md` § `materials.md`.

### The four roles

- **`key`** — a downstream reader should open this. It teaches something no other material teaches
  as well. A small minority of a real archive.
- **`redundant-of m<nnn>`** — it teaches the same thing as the named row, no better: second copies,
  four notebook sets that are the same course, a slide deck restating the notes.
- **`peripheral`** — it is about something else: an adjacent topic, another project, courseware for a
  different course. Not a quality judgment — the next topic's `key` lives here.
- **`off-topic`** — it belongs to **this** archive but should not be read at all: a tool error
  screenshot, an unrelated admin file. Off-topic rows are the gate's subject (Step 6).

A row's role is about **this archive**, not about the world.

## Steps

### 1 — Manifest, then inventory

**Before any write**, capture the manifest — the mechanism behind the read-only proof, the `sha256`
cells and re-run drift, all three:

```bash
ARCHIVE=<absolute archive root>
KB=<absolute instance root>
MANIFEST_BEFORE=$(mktemp -t map-before.XXXXXX)
SESSION_MARKER=$(mktemp -t map-session.XXXXXX)      # the session-start anchor, outside the archive

touch "$SESSION_MARKER"                             # done BEFORE any read or write
python3 - "$ARCHIVE" <<'PY' > "$MANIFEST_BEFORE"
import hashlib, os, sys
root = sys.argv[1]
rows = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames
                   if d not in {'.git', '__pycache__', '.ipynb_checkpoints'}]
    for name in filenames:
        if name in {'.DS_Store', 'Thumbs.db', 'materials.md'} or name.endswith('.tmp'):
            continue
        p = os.path.join(dirpath, name)
        rel = os.path.relpath(p, root)
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        rows.append(f"{h.hexdigest()}\t{int(os.path.getmtime(p))}\t{rel}")
print("\n".join(sorted(rows, key=lambda r: r.split(chr(9), 2)[2])))
PY
```

Then inventory filenames — recursive, junk excluded. This count is the denominator every later step
is checked against:

```bash
find "$ARCHIVE" -type f \
  ! -name '.DS_Store' ! -name 'Thumbs.db' ! -name '*.tmp' \
  ! -path '*/.git/*' ! -path '*/__pycache__/*' ! -path '*/.ipynb_checkpoints/*' \
  | sed "s|^$ARCHIVE/||" | sort
wc -l < "$MANIFEST_BEFORE"          # the denominator
```

Report it compressed: top-level folders with counts, loose files by name. A folder with more than
~20 files of one kind is a bulk folder and a candidate for a single row.

If `$KB_PATH/materials.md` already exists, read it first — this is a re-run, and Hard Rules 6 and 10
apply.

A **folder digest** for a folder row comes from the same manifest — the sha256 of the
`«file sha256»\t«archive-relative path»` lines for the files the row covers (the remainder), sorted by
hash then path, joined by newlines with a trailing newline:

```bash
# all files under images/, minus any path that has its own exception row (here: the 11 off-topic images)
awk -F'\t' -v p='images/' '$3 ~ "^"p {print $1"\t"$3}' "$MANIFEST_BEFORE" | sort | shasum -a 256
```

For a plain folder the filter is just the prefix; for a mixed folder, drop the exception paths first
so the count and digest match the remainder.

`$SESSION_MARKER` (touched above, outside the archive) is the mtime anchor for the
`find -newer` assertion in Step 7.

### 2 — Sort relevant from peripheral (topic-focused)

With the topic known, classify by path and name **before** deep reading:

- **Likely relevant** — directly addresses the topic
- **Possibly relevant** — mixed folders, ambiguous naming
- **Likely peripheral** — clearly another topic or an adjacent area
- **Likely off-topic** — junk that happens to live in this archive

### 3 — Read relevant material deeply, peripheral material lightly

- **Likely relevant:** read notes, READMEs and link lists **in full**; skim papers and notebooks to
  the title and first heading/cell — enough for `kind` and a `concepts` line, not a summary. Write
  detailed `concepts` cells from actual content. Row a long note per `##` section when the sections
  have different fates.
- **Likely peripheral / off-topic:** categorize from filename and folder, and say in `concepts` why.
- **Possibly relevant:** quick inspection, then deep or light as it turns out.
- **Images:** do not open them beyond the filename, unless a cryptic name sits in an otherwise `key`
  folder.

### 4 — Find the duplicates

This is the step that pays for the skill. Duplicates hide in four shapes:

| Shape | How it shows |
| :-- | :-- |
| Same file twice | different filenames, identical bytes — free, straight from the manifest |
| Same source, different medium | slides restating the notes |
| A set from one course | N notebooks from the same lesson series |
| A section restating another | inside one note: `## PE` and `## 位置编码补充` |

Byte-identical pairs come from the manifest's repeated hashes. The other three need titles. For a
set, pick one canonical `key` row and make the rest `redundant-of` it — do not make them all `key`
because they differ slightly. **Say what a redundant copy adds**, if anything, in its `concepts`
cell; a set member with genuinely unique content is its own `key` row.

### 5 — Assign roles and build the rows

Work top-level folder by top-level folder:

- Whole folder about another topic → one `peripheral` row, `path` ending `/**`, with its file count
  and the one line saying why.
- A mixed folder (bulk on-topic, scattered exceptions) → one row for the bulk plus a row per
  exception.
- Otherwise row its files (or its note sections), assign `key` or `redundant-of`, and write
  `concepts` from what you actually read.

Set `sha256` from the manifest: a file or section row takes its own file's hash; a folder row takes
the folder digest (the **remainder** digest when the folder has exception rows). Set `flags` where
Step 3 or the ref scan found a problem:

```bash
# broken relative link/image targets, per file — a target that does not resolve from that file's location
# covers any extension (images, .md, .ipynb, extensionless) and skips absolute URLs, mailto: and anchors
grep -rhoE '\]\(([^)]+)\)' "$ARCHIVE" --include='*.md' \
  | sed -E 's/^\]\(//; s/\)$//' \
  | grep -vE '^(https?:|mailto:|#)' | sort -u
```

### 6 — Gate: confirm the off-topic exclusions

Before writing anything, show the user the **`off-topic` rows only** — one line each: path and the
reason. Also state the row counts and the duplicate sets found. Then wait for the answer.

```text
Off-topic (proposed for exclusion — not read by any later stage):
  images/Claude API 503 Error.png            — tool error screenshot
  images/Direct RPA and Agent Migration Roadmap.png — another topic's diagram
  ...
Rows: 41 · files covered: 156/156 · duplicates: 3 sets
Confirm these exclusions, or name any that should stay in scope.
```

If the user keeps one, re-role it (`peripheral` or `key`) and say so in the report. This is the
run's first agreement; nothing is written before it.

### 7 — Write the map, prove the archive untouched, report

Write `$KB_PATH/materials.md` with the header (`archive:` line, counts) and all rows.

Then the read-only proof — recompute the manifest and diff, **and** assert no file is newer than the
session start:

```bash
MANIFEST_AFTER=$(mktemp -t map-after.XXXXXX)
# ... the same python block as Step 1, into "$MANIFEST_AFTER" ...
diff "$MANIFEST_BEFORE" "$MANIFEST_AFTER"    # expect no output

# the mtime assertion the knowledge model names: expect no output
find "$ARCHIVE" -type f -newer "$SESSION_MARKER" \
  ! -name '.DS_Store' ! -name 'Thumbs.db'

rm -f "$MANIFEST_BEFORE" "$MANIFEST_AFTER" "$SESSION_MARKER"
```

The two checks are not redundant: the manifest diff is **content-level** (it catches an edit that
preserved mtime, and files added or removed), while `find -newer` is the plain mtime assertion the
model states. Both must come back empty.

On a **re-run**, diff the before-manifest against the *previous* run's manifest keyed by `path` and
apply the re-run rules: unchanged hash → keep the row; changed hash → refresh `sha256`, re-read, and
refresh `concepts`/`role`/`flags` while keeping the `id`; new file → new row and id; a path absent
from the new manifest → keep the row, add `missing`.

Then report:

- Rows written against the file denominator, and the residue if any.
- key / redundant / peripheral / off-topic counts.
- The duplicate sets found, one line each — the finding to argue with.
- Flags raised: broken links, nested headings, unreadable files, `missing` rows.
- Peripheral folders named, with counts: what a future topic inherits.
- The manifest diff result (expected empty).

Nothing about the mapping is persisted except `materials.md`.

## Contract test

Given a fixture archive containing a duplicate pair, an off-topic folder, a flat mixed `images/`
folder with one off-topic file, and a multi-section note:

- every file is covered by a row or an ancestor folder row (rows + folder-row file counts equal the
  denominator);
- the duplicate's second copy is `redundant-of` the first and names its id;
- the off-topic folder is a single `peripheral` row ending `/**` with a file count, not one row per
  file; the off-topic file inside the mixed `images/` folder has its own `off-topic` row while the
  rest of the folder is one ancestor row;
- the multi-section note produced one row per `##`, each carrying the same file `sha256`;
- every `key` row's `concepts` cell is non-empty, every `used-in` cell is `—`, every `sha256` is
  64 hex characters, and the folder row's `sha256` is a manifest digest;
- `$KB_PATH/materials.md` exists with the `archive:` header and counts; **no other file was
  created** and the fixture is byte-identical (manifest diff empty, no file newer than session
  start);
- a second run adds no duplicate ids, preserves every existing id, `concepts` and `used-in`, keeps a
  deleted file's row with `missing`, and refreshes only changed rows;
- the `off-topic` gate list was printed before the writing step.

## Handoffs

**In:** an absolute archive path, an explicit `$KB_PATH`, and the topic. Nothing else — this skill
reads no other product's file.

**Out:** `$KB_PATH/materials.md` → `clean-notes` restructures the archive into `notes/` from it;
`llm-wiki-ingest` later reads the `mat:` ids through the notes; `llm-wiki-lint` checks the `sha256`
column for drift.

**Boundaries:**
- vs `clean-notes`: this inventories and never edits content; that rewrites material into `notes/`.
- vs `llm-wiki-ingest`: that bootstraps `SCHEMA.md`/`narrative.md`/`sources.md` and writes the wiki.
- vs `archive-materials` (Writing Assistant): that runs **after** a piece ships and fills `used-in` in
  this same file — one writer per column; this skill never writes that column and its re-runs leave
  it untouched.
