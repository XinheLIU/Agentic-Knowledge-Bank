---
name: llm-wiki-init
description: "Karpathy's LLM Wiki: initialize a new wiki from scratch with proper directory structure, SCHEMA.md, index.md, log.md, and git. Use when the user asks to 'create a wiki', 'start a knowledge base', 'set up a wiki', or mentions starting a new KB from nothing. Ask about the wiki's domain before scaffolding — the answer drives the tag taxonomy and page thresholds."
license: MIT
metadata:
  hermes:
    tags: [wiki, knowledge-base, setup]
    category: research
    related_skills: [llm-wiki, llm-wiki-lint]
---

Last updated: 2026-09-01

# Karpathy's LLM Wiki — Init

First-time setup of a new wiki. Run once.
See `llm-wiki-ingest` for daily ingest and `llm-wiki-lint` for health checks.

## When This Skill Activates

- Asking to create, start, or initialize a wiki or knowledge base
- No wiki exists yet at the target path

## Steps

### 1. Determine the wiki path

Check `$WIKI_PATH` env var. If unset, default to `./wiki`. (in current working directory) . Confirm with the user.

### 2. Create directory structure

```bash
WIKI="${WIKI_PATH:-./wiki}"
mkdir -p "$WIKI"/{entities,concepts,comparisons,queries}
mkdir -p raw/{articles,papers,transcripts,assets}
```

`raw/` and `wiki/` are siblings at the project root — not nested.

### 3. Initialize git

```bash
cd "$WIKI"
git init
printf ".obsidian/workspace*\n.obsidian/plugins/\n" >> .gitignore
```

### 4. Ask the user what domain the wiki covers

Be specific — "AI/ML research" not "tech". The answer drives tag taxonomy and page
thresholds in SCHEMA.md.

Also ask the **body language** — the language all page prose is written in, independent of
source language. Default to English; offer Chinese only if the user says the wiki's working
language is Chinese. This fills the Language Policy block below.

### 5. Write SCHEMA.md

```markdown
# Wiki Schema

Last updated: YYYY-MM-DD

## Domain
[What this wiki covers]

## Language Policy
- **Body language:** [English | Chinese] — the language ALL page body prose is written in,
  independent of source language. Default: English.
- Sources in any language are translated into the body language. Keep canonical domain terms
  with the original in parens on first use: "regularization (正则化)".
- Filenames follow the slug convention below regardless of body language.
- If translating would force large verbatim blocks (quotes, untranslatable passages) into the
  body, keep the original inline and add an English gloss — do not silently switch the page.

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md` under the correct section
- Every action must be appended to `log.md`
- On pages synthesizing 3+ sources, append `^[../raw/articles/source.md]` to paragraphs
  whose claims trace to a specific source

## Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  type: entity | concept | comparison | query
  tags: [from taxonomy below]
  sources: [../raw/articles/source-name.md]
  confidence: high | medium | low   # optional — use for opinion-heavy or single-source claims
  contested: true                   # optional — set when unresolved contradictions exist
  contradictions: [other-page-slug] # optional
  ---
  ```

### raw/ Frontmatter
  ```yaml
  ---
  source_url: https://example.com/article
  ingested: YYYY-MM-DD
  sha256: <hex digest of body below this frontmatter>
  ---
  ```
  sha256 is required on all raw files — enables skip logic on re-ingest and drift detection.

## Tag Taxonomy
[Define 10-20 tags. Add new tags here BEFORE using them on pages.]

Rule: every tag on a page must appear here. This prevents tag sprawl.

## Page Thresholds
- **Create** when entity/concept appears in 2+ sources OR is central to one source
- **Update existing** when a source mentions something already covered
- **Don't create** for passing mentions or things outside the domain
- **Split** pages over ~200 lines into sub-topics with cross-links
- **Archive** when content is fully superseded — move to `_archive/`, remove from index

## Concept Granularity
A page = one atomic concept: the smallest unit worth understanding on its own.
- A parent concept and its sub-variants stay on ONE page; variants are `##` sections.
  e.g. regularization → ridge / lasso / elastic-net are sections, not separate pages.
       generalized linear models → logistic / softmax / Poisson are sections.
- A variant GRADUATES to its own page only when it clearly earns independence:
  (a) it appears in 2+ sources independent of the parent, OR
  (b) it has ~60+ lines of distinct content (own derivation, tradeoffs, cases), OR
  (c) 3+ other pages need to [[link]] specifically to it, not the parent.
- **Default when uncertain: fold into the parent.** Under-splitting is cheap to fix later;
  over-splitting scatters one idea across thin stubs.

## Update Policy
When new information conflicts with existing content:
1. Check dates — newer sources generally supersede older ones
2. If genuinely contradictory: note both positions with dates and sources
3. Mark in frontmatter: `contested: true`, `contradictions: [page-name]`
4. Flag for user review in lint report
```

### 6. Write index.md

```markdown
# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: YYYY-MM-DD | Total pages: 0

## Entities
<!-- Alphabetical within section -->

## Concepts

## Comparisons

## Queries
```

**Scaling rule:** When any section exceeds 50 entries, split into sub-sections by first
letter or sub-domain. When index exceeds 200 entries, create `_meta/topic-map.md`.

### 7. Write log.md

```markdown
# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, update, query, lint, create, archive, delete
> When this file exceeds 500 entries, rotate: rename to log-YYYY.md, start fresh.

## [YYYY-MM-DD] create | Wiki initialized
- Domain: [domain]
- Structure created with SCHEMA.md, index.md, log.md
```

### 8. Confirm and suggest

Tell the user:
- Wiki path and git status
- Suggest first sources to ingest (`llm-wiki-ingest` skill handles ingest)
- Remind them to add SCHEMA.md to git: `git add SCHEMA.md index.md log.md && git commit -m "init: wiki"`
