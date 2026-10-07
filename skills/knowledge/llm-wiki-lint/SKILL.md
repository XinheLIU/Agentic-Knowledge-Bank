---
name: llm-wiki-lint
description: "Karpathy's LLM Wiki: run a full health-check audit covering broken links, orphans, index gaps, frontmatter validation, source drift, stale content, and tag sprawl. Use when the user says 'lint', 'audit', 'health-check', 'review the wiki', 'check for broken links', or asks about wiki maintenance. Use proactively after major ingests or before querying a wiki that hasn't been checked recently."
license: MIT
metadata:
  hermes:
    tags: [wiki, knowledge-base, maintenance, audit]
    category: research
    related_skills: [llm-wiki, llm-wiki-init]
---

Last updated: 2026-09-01

# Karpathy's LLM Wiki — Lint & Maintenance

Periodic health checks and audits for an existing wiki.
See `llm-wiki` for ingest/query and `llm-wiki-init` for first-time setup.

## When This Skill Activates

- Asking to lint, audit, health-check, or review the wiki
- Asking for broken links, orphan pages, or stale content
- Asking to rotate the log

## Wiki Location

```bash
WIKI="${WIKI_PATH:-./wiki}"
```

## Orientation (always first)

① Read `SCHEMA.md` — conventions and tag taxonomy.
② Read `index.md` — current page inventory.
③ Scan last 30 lines of `log.md` — recent activity.

## Triage (always after orientation, before checks)

Before running the full checklist, do a quick triage to guide priorities:

1. Compare `index.md` entries against filesystem — if the index lists pages that don't exist on
   disk (ghost entries), the top recommendation should be **re-run ingest** to restore them, not
   "create N individual pages."
2. Check if `concepts/` is empty or nearly empty while `index.md` lists many concepts — this is
   a strong signal of an incomplete prior ingest.
3. Scan for raw files in ALL `raw*` directories (not just `raw/`) when checking for missing sha256.

Run all 14 checks afterward, but use the triage to weight the report's executive summary and to
avoid recommending micro-fixes for systemic problems.

## Lint Checks

Run all checks, then report grouped by severity. Each check is tagged with its actionability:
`[auto-fix]` = safe to fix without asking; `[human-review]` = flag and suggest; `[info]` = report
only, no action expected.

### 1. Broken wikilinks [human-review]
Find `[[links]]` pointing to pages that don't exist.
```bash
# For each .md in entities/ concepts/ comparisons/ queries/:
# Extract all [[wikilink]] targets → check if matching .md file exists
```

### 2. Orphan pages [info]
Pages with zero inbound `[[wikilinks]]` from other wiki pages.
```python
import os, re
from collections import defaultdict
wiki = "<WIKI_PATH>"
inbound = defaultdict(set)
for root, _, files in os.walk(wiki):
    for f in files:
        if not f.endswith(".md"): continue
        path = os.path.join(root, f)
        text = open(path).read()
        for link in re.findall(r'\[\[([^\]]+)\]\]', text):
            inbound[link].add(path)
# Pages with no entry in inbound are orphans
```

### 3. Index completeness [human-review]
Every wiki page in `entities/`, `concepts/`, `comparisons/`, `queries/` must appear in
`index.md`. Compare filesystem against index entries.

### 4. Frontmatter validation [auto-fix]
Every wiki page must have: `title`, `created`, `updated`, `type`, `tags`, `sources`.
Tags must all appear in the SCHEMA.md taxonomy.

### 5. Source drift [human-review]
For each file in `raw/` with a `sha256:` frontmatter field: recompute the hash over the
body (everything after the closing `---`) and flag mismatches.
Mismatch = raw file was edited (violates immutability) or URL content changed on re-ingest.

### 6. Stale content [info]
Pages whose `updated` date is >90 days older than the most recent source mentioning the
same entities. Flag for user review, not auto-update.

### 7. Contested pages [human-review]
Surface all pages with `contested: true` or non-empty `contradictions:` frontmatter.
These require human resolution before claims harden into accepted fact.

### 8. Quality signals [info]
- Pages with `confidence: low`
- Pages citing only a single source with no `confidence` field set
These are candidates for finding corroboration or demoting to `confidence: medium`.

### 9. Page size [info]
Flag pages over 200 lines — candidates for splitting into sub-topics with cross-links.

### 10. Tag audit [auto-fix]
List all tags in use across wiki pages. Flag any not in the SCHEMA.md taxonomy.

### 11. Log rotation [auto-fix]
If `log.md` exceeds 500 entries: rename to `log-YYYY.md` (use the year of the first entry),
start a fresh `log.md` with a rotation note. Confirm with user before rotating.

### 12. Missing sha256 on raw files [auto-fix]
Every file in `raw/` should have a `sha256:` frontmatter field. Flag any that don't —
they can't participate in the skip/drift detection logic.

### 13. Language consistency [human-review]
Body prose must be in the SCHEMA body language (Language Policy). For each wiki page, flag
prose that has actually drifted into another language — NOT bare canonical terms or book
titles, which are expected. Inline glosses like `财商` and titles like `《财商训练40讲》` are
fine; flag only genuine foreign-language clauses.

Heuristic when body language is English (two signals, flag on either):
```python
import re
fence = chr(96) * 3                       # avoid a literal triple-backtick in this block
s = re.sub(r'%s.*?%s' % (fence, fence), '', text, flags=re.DOTALL)  # drop fenced code
s = re.sub(r'\[\[[^\]]+\]\]|`[^`]+`', '', s)                        # drop wikilinks + inline code
# signal 1: CJK sentence punctuation = real Chinese clauses (book titles 《》 excluded)
s_nobook = re.sub(r'《[^》]*》', '', s)
drift = re.search(r'[，。、；：！？“”（）]', s_nobook)
# signal 2: any prose line >30% CJK characters (paragraph-level drift)
dense = any(len(l.strip()) >= 10 and
            len(re.findall(r'[一-鿿]', l)) / len(l.strip()) > 0.30
            for l in s.splitlines())
flagged = bool(drift or dense)
```
A bare repeated term like `财商` in otherwise-English prose is NOT drift — do not flag it.
Report path + offending snippet + "rewrite to {body_language}". Do not auto-rewrite.

### 14. Concept granularity — should-fold [human-review]
Detect pages that fail the SCHEMA graduation criteria and should be folded into a parent
page (see Concept Granularity in SCHEMA). Two detection paths:

**Path A — Sibling variants (over-fragmentation):** 2+ page titles read as *variants or
instances of a shared parent concept* — e.g. `ridge` / `lasso` / `elastic-net` under
regularization, or `logistic-regression` / `softmax-regression` under
generalized-linear-models. This is an agent judgment, not a keyword match.

Corroborating signals (raise confidence, do not trigger alone): the candidates are thin
(<40 lines), share tags, and either mutually `[[link]]` or all `[[link]]` a common parent
page. Use these to confirm, not to select.

**Path B — Solo thin page failing all graduation criteria:** A single page that meets NONE
of the three SCHEMA graduation thresholds:
- (a) NOT in 2+ independent sources
- (b) Under ~60 lines of distinct content
- (c) Fewer than 3 other pages [[linking]] to it (excluding index.md)

A page failing all three criteria has no justification for independence — flag it for
folding into the most relevant parent concept page.

**Do NOT flag distinct co-tagged concepts.** Pages sharing a tag (e.g. `asset-types`,
`pseudo-assets`, `cost-framework` all tagged `investment-principles`) are separate atomic
concepts, not variants — leave them alone. Size and shared tags alone are never sufficient.

Report the cluster (Path A) or solo page (Path B) + suggested merge target. Do not
auto-merge — folding rewrites prose and is a human decision.

### 15. Concept granularity — should-graduate [human-review]
Detect `##` sections within pages that meet SCHEMA graduation criteria but are still folded
(see Concept Granularity in SCHEMA). This is the reverse of check 14.

For each wiki page with `##` sections, evaluate whether any section meets the graduation
thresholds:

- **Signal 1 — Content mass:** The section body (from its `###`/`##` heading to the next
  same-or-higher-level heading) is ~60+ lines.
- **Signal 2 — Source independence:** The section's topic appears in 2+ entries of the
  page's `sources:` frontmatter, OR is mentioned in distinct raw files.
- **Signal 3 — Inbound link demand:** 2+ other wiki pages [[link]] to this parent page with
  anchor text or context that specifically targets this section's topic (not the parent
  concept broadly). Check wikilink context in referring pages — a link like
  `[[parent-page#section-topic]]` or prose like "see also [[parent-page]] for its X
  variant" are strong signals.

**Trigger:** Signal 1 alone is enough to flag (a section that large warrants review).
Signal 2 or 3 + Signal 1 together = strong recommendation to graduate.

Report the parent page + section heading + which signals fired + suggested new page
filename. Do not auto-graduate — splitting rewrites prose and is a human decision.

### 16. CLAUDE.md wiki routing [auto-fix]

Check whether the project has a CLAUDE.md (at `./CLAUDE.md` or `./.claude/CLAUDE.md`) that
routes ML domain questions through the wiki.

**Detection:**
1. Look for `CLAUDE.md` at project root first, then `.claude/CLAUDE.md`.
2. If neither exists → flag as missing. Create `CLAUDE.md` at project root with the routing
   rule + wiki structure summary.
3. If one exists but doesn't mention the wiki (`wiki/`, `index.md`, `SCHEMA.md`) → flag as
   incomplete. Append the routing rule to the existing file.

**Auto-fix content (when creating):**
```markdown
# Project: LLM Wiki — {domain} Knowledge Base

Last updated: {today}

## Wiki Routing Rule

**Before answering ANY question about {domain} in this project:**

1. Read `wiki/index.md` to identify relevant pages
2. Search `wiki/` for the topic (keyword or semantic)
3. Synthesize from wiki pages first — cite them with `[[wikilinks]]`
4. Only fall back to general knowledge if the wiki has nothing on the topic
5. If the answer reveals something generalizable not yet in the wiki, file it to
   `wiki/concepts/` and update `wiki/index.md` and `wiki/log.md`

This overrides the default behavior of answering from training data. The wiki is the primary
knowledge source for {domain} questions in this project.

## Wiki Structure

- `wiki/SCHEMA.md` — conventions, tag taxonomy, page thresholds
- `wiki/index.md` — content catalog with one-line summaries
- `wiki/log.md` — chronological action log
- `wiki/concepts/` — topic pages
- `wiki/entities/` — people, orgs, models
- `wiki/queries/` — filed query results
- `raw/articles/` — immutable source material
```

**Auto-fix content (when appending to existing):**
Append the routing rule section only (from "## Wiki Routing Rule" through the rule bullets),
preceded by a `---` separator.

Fill `{domain}` from SCHEMA.md's Domain field. Fill `{today}` with current date.

## Report Format

Group findings by severity:

```
## Lint Report — YYYY-MM-DD

### Critical
- Broken wikilinks: N (list each)

### High
- Orphan pages: N (list each)
- Source drift: N (list each with old vs new hash)

### Medium
- Missing/Incomplete CLAUDE.md wiki routing: yes/no (+ action taken)
- Contested pages: N (list with contradiction links)
- Missing sha256 on raws: N
- Language-inconsistent pages: N (list with offending snippet)

### Low
- Stale content: N (list with last-updated date)
- Confidence: low pages: N
- Pages over 200 lines: N
- Unknown tags: N
- Should-fold pages: N (list each page/cluster + suggested merge target)
- Should-graduate sections: N (list each section + which signals fired)

### Info
- Index gaps: N (in filesystem but not index, or vice versa)
- Log rotation needed: yes/no
```

For each finding: file path + specific issue + suggested action.

## After Linting

Append to `log.md`:
```
## [YYYY-MM-DD] lint | N issues found (X critical, Y high, Z medium)
```
