---
name: llm-wiki-ingest
description: "Karpathy's LLM Wiki: ingest (distill) a source — article, paper, transcript, URL, pasted note — into the wiki. Captures the source to raw/ with a body sha256, runs a two-pass extract→write flow with a Socratic takeaway discussion before filing, then writes entity/concept/comparison pages and updates index.md and log.md. Use when the user says 'ingest this', 'add this to my wiki', 'distill this article/paper into the wiki', 'process this source', or hands over a source for the knowledge base. Purely file-based — no desktop app, no HTTP API (querying the LLM Wiki desktop app is the separate `llm-wiki` skill). Never writes Learning OS `learning/`."
license: MIT
metadata:
  hermes:
    tags: [wiki, knowledge-base, ingest, distillation]
    category: research
    related_skills: [llm-wiki-init, llm-wiki-lint, llm-wiki-book]
---

Last updated: 2026-09-01

# Karpathy's LLM Wiki — Ingest

The daily driver: distill one source into the wiki. Capture → extract → discuss → write.
A single source may touch 10–15 pages — that's normal and the point.
See `llm-wiki-init` for first-time setup, `llm-wiki-lint` for health checks.

## When This Skill Activates

- The user hands over a source (file, URL, pasted text) to add to the wiki
- "Ingest this", "distill this into my wiki", "process these papers"

**Not this skill:** querying the LLM Wiki desktop app's HTTP API (`llm-wiki`),
scaffolding a new wiki (`llm-wiki-init`), Learning OS distillation (never write `learning/`).

## Steps

### 1. Locate the wiki and orient

```bash
WIKI="${WIKI_PATH:-./wiki}"
```

- No `$WIKI/SCHEMA.md` → stop and suggest `llm-wiki-init`. Never ingest into an unschema'd directory.
- Resolve the raw root: sibling `raw/` next to `$WIKI` (init's layout), else `$WIKI/raw/` if that's what exists. Match whichever the wiki already uses.
- Read, in order: `SCHEMA.md` (conventions, tag taxonomy, thresholds, language policy) → `index.md` (what already exists) → last 30 lines of `log.md` (recent activity).

### 2. Capture to raw/

File the source under `raw/articles/` (web posts, notes), `raw/papers/`, or `raw/transcripts/`; images go to `raw/assets/`. For URLs, fetch and save the content as markdown. Filename: lowercase, hyphens.

Prepend raw frontmatter, hashing the body (everything after the closing `---`):

```yaml
---
source_url: https://example.com/article
ingested: YYYY-MM-DD
sha256: <hex digest of body below this frontmatter>
---
```

```bash
python3 -c '
import hashlib, re, sys
text = open(sys.argv[1]).read()
body = re.split(r"^---\s*$", text, maxsplit=2, flags=re.M)[2].lstrip("\n")
print(hashlib.sha256(body.encode()).hexdigest())' raw/articles/source-name.md
```

**Raw files are immutable from this point.** Never edit a raw body — that is what the wiki layer is for, and lint treats a hash mismatch as drift.

### 3. Differential check (skip logic)

If this source was ingested before (same `source_url` or filename in raw/):

- **Body hash unchanged** → append `## [YYYY-MM-DD] ingest | <Title> (skipped — unchanged)` to `log.md` and stop.
- **Body hash changed** → proceed as a re-ingest: update the raw file's `sha256` and `ingested` date, and note the drift in the log entry so lint doesn't flag it later.

### 4. Pass 1 — Extract (read-only)

Read the full source. Produce a structured extraction — no writes yet:

| Candidate | Type | Verdict | Target page | Why |
|---|---|---|---|---|
| RoPE | concept | update | `concepts/rope.md` | already covered; source adds scaling laws |
| Sub-variant X | concept | fold | parent page `##` section | fails graduation (a)(b)(c) |

- Apply SCHEMA's **Page Thresholds** (create at 2+ sources or central-to-source; skip passing mentions) and **Concept Granularity** (default: fold into parent).
- For every `update` verdict, open the target page and check for contradictions against the source — compare claims, not titles.
- **Long sources (roughly >500 lines, or multi-chapter):** split by section and dispatch parallel subagents, one per section, each returning only a candidate table. Merge and dedupe against `index.md`. Subagents extract; they never write.

### 5. Discuss takeaways (the gate)

Before writing anything, present to the user:

- 3–7 key takeaways from the source
- The proposed diff: N pages to create, M to update, K contradictions found
- Ask what to emphasize, drop, or reframe

Wait for the user's answer, then write. **Batch exception:** when ingesting a pre-approved list of sources, the user may waive the gate once up front — say so in the log entries.

### 6. Pass 2 — Write

Create and update pages under `entities/`, `concepts/`, `comparisons/` per SCHEMA:

- Full frontmatter: `title`, `created`, `updated`, `type`, `tags`, `sources` (path to the raw file, matching the path style existing pages use). Bump `updated` on every edit.
- Tags come from the SCHEMA taxonomy **only**. Need a new tag? Add it to SCHEMA.md first, then use it.
- Minimum 2 outbound `[[wikilinks]]` per page; write body prose in the SCHEMA body language.
- On pages synthesizing 3+ sources, append `^[<raw path>]` footnotes to paragraphs whose claims trace to a specific source.
- **Contradictions — never silently overwrite.** Follow SCHEMA's Update Policy: keep both positions with dates and sources, set `contested: true` and `contradictions: [other-page-slug]`, and tell the user. Lint surfaces these for resolution.

Then, in the same pass:

- **index.md** — one entry per new page under its section (alphabetical), with a one-line summary; bump the header's `Last updated` and `Total pages`.
- **log.md** — append:

```markdown
## [YYYY-MM-DD] ingest | <Source Title>
- Raw: raw/articles/source-name.md
- Created: [[page-a]], [[page-b]]
- Updated: [[page-c]] (added scaling-law section), [[page-d]]
- Contested: [[page-e]] ↔ [[page-f]]
```

### 7. Report and suggest

Tell the user:

- Raw path, pages created/updated (with links), contradictions flagged, any taxonomy additions
- Remind: run `llm-wiki-lint` every 5–10 ingests
- Suggest a commit (`git add -A && git commit -m "ingest: <source title>"`) — never run it yourself

## Hard Rules

- **You MUST NOT** edit a raw file's body after capture.
- **You MUST NOT** write to Learning OS `learning/` — the wiki/learning wall.
- **You MUST NOT** use a tag that isn't in the SCHEMA taxonomy.
- **You MUST NOT** create or update a page without updating `index.md` and `log.md` in the same pass.
- **You MUST NOT** write wiki pages before the takeaway discussion, unless the user waived the gate for a batch.
- **You MUST NOT** call any HTTP API — this skill is files only.
