# Plan: Re-position Agentic-Knowledge-Bank as a provenance-tracked concept wiki

Last updated: 2026-10-09

Status: **complete** — Phases A–C done and verified (the Transformer run passed every structural acceptance criterion; ticket 18 folded its findings back into the model and the skills). **Phase D is done as of 2026-10-09**: the four KB skills are reassociated in Skills Manager against the committed public repository (IDs, presets and deployments retained; `llm-wiki-init` and `organize-docs` retired), a fresh export reproduces the discovery links, and the stale collector description is corrected in the GitHub Profile README. The only deferred item is Writing Assistant's own manager entries (`archive-materials`, `llm-wiki-book`), which wait on that repository's first commit. No git write operations were performed without the explicit Phase D request.

## Context

The repo still carries three generations: the retired LangGraph collector, the Horizon/SQLite admission store (`kb/`, MCP, UI), and a generic Karpathy LLM-Wiki skill slice. None of them deliver the two goals you now want:

1. **Cognitive asset accumulation**: a wiki derived from your raw notes, where every claim is traceable to a raw note or to an authoritative primary source.
2. **Cognitive compounding**: deferred to step 2. Draft material is kept but not designed in this plan.

Plain LLM-Wiki produced **119 pages for one topic** — a granularity failure, not a per-source page model: the skills already minted one atomic concept per page, so `rope` and `moe-router` sat as peers of `attention`. It has no MECE restructure stage, no narrative spine, and no depth model. The new design adds three things: hierarchical classification, a **horizontal thread** (relations between concepts) and a **vertical L1–L4 depth model** inside each concept, plus supplementation from authoritative sources. Before any page is written, the narrative and the granularity are agreed with you at a gate on every run.

Decisions already made: MISI = **MECE**. Retire `kb/` by **moving it into information-assistant**, its only consumer. Remove `organize-docs` and `llm-wiki-init`. Rewrite `llm-wiki-ingest` in place. Move `archive-materials` to writing-assistant. Keep `map-materials` and rewrite it as the intake inventory. Gate every run.

---

## Phase A: Repositioning and legacy removal (repo)

**A1. Positioning docs** → verify: no doc mentions admission/Horizon/SQLite as an AKB responsibility
- Rewrite `README.md` / `README.zh-CN.md`: the two purposes, pipeline diagram (raw → inventory → MECE notes → wiki), and a relationship table:

| Product | Relation to AKB |
|---|---|
| Information Assistant | Upstream. Discovers sources and owns the info-stream asset store (after A2). Its outputs can become raw input here. |
| Learning OS | Downstream. Reads wiki pages as study material and owns attempts/mastery. Never writes to the wiki. |
| Writing Assistant | Downstream. Takes wiki pages and `materials.md` as sourced material, and owns `archive-materials`. |
| Synapse | Derived cross-source index over published wiki pages. |

- Rewrite `AGENTS.md`, `docs/architecture.md` and `project-vision.md` (v0.3) to match. Replace `docs/domain-invariants.md` with the wiki invariants from B1.

**A2. Move `kb/` and its runtime surface to information-assistant** → verify: `uv run pytest` passes in information-assistant, and AKB contains no `kb` import
- Move as working-tree files so the **8 uncommitted modifications in `kb/` are preserved**: `kb/`, `mcp_knowledge_server.py`, `ui/`, the `kb`-related `tests/` + `tests/fixtures/`, `CONTEXT.md` (admission vocabulary), `docs/product/ai-kb/`, `docs/adr/0001-*`, and the old `docs/domain-invariants.md`.
- information-assistant: in `pyproject.toml`, drop the `ai-kb` path dependency and package `kb` locally. Its imports (`operator.py`, `production.py`, `digest/*`, tests) keep the `kb.` namespace, so no code edits are needed.
- AKB: drop the Python package from `pyproject.toml`, or reduce it to an empty dev env if `scripts/export-skills.py` needs one. Add a CHANGELOG entry recording the move.
- No git operations unless you ask. information-assistant has no commits yet.

**A3. Delete unrelated legacy** ✅ (executed 2026-10-08 by ticket **Remove unrelated legacy**) → verify: `git status` shows only intended deletions, and no maintained doc links a deleted path
- Removed the retired-pipeline agent/tool copies (`.opencode/`, `opencode.json`) and the repo-local OpenSpec skill copies plus broken MCP configs under `.claude/` and `.codex/` (OpenSpec is installed globally).
- Removed the `patterns/` demo code and the ignored cutover-rehearsal scratch folder.
- Removed the retired-plan document archive, the pre-split instruction sheet and the sibling-repo failure log.
- Extracted `TODO.md`'s 认知复合引擎 epic and 泛读/精读 learning model into `docs/compounding/draft.md` (step-2 input), then deleted `TODO.md`.
- `tests/test_legacy_retirement.py` is removed with the move (ticket **Execute the kb move into Information Assistant**).
- Still owned by a later cleanup: `.scratch/horizon-kb-design/`, the previous effort's map and tickets.
- The retired P2–P5 execution plan folded into Phase D and was deleted; its four inbound references are repaired by ticket **Rewrite the positioning docs** and its two `catalog/*.json` `"plan"` fields by ticket **Triage the skill set**.

**A4. Skill set triage** → verify: each `catalog/skill-set.json` matches the `SKILL.md` dirs on disk, and a grep finds no dangling references to removed skills
- Delete `skills/knowledge/organize-docs`, `skills/knowledge/llm-wiki-init`
- Move `archive-materials` → `writing-assistant/skills/writing/operations/archive-materials`, and update both catalogs.
- Regenerate discovery links (`.claude-plugin/skills/`) from the catalog. Skills-manager reassociation stays pending (P2, gated on repo commits), as it already is.
- Final KB set: `map-materials`, `clean-notes`, `llm-wiki-ingest`, `llm-wiki-lint`

---

## Phase B: Knowledge model and skill redesign

### B1. Spec: `docs/knowledge-model.md` (the single source the 4 skills cite)

**Instance layout.** One KB per domain, external to the repo, e.g. `~/Documents/Personal-Projects/Learning/Transformer/Transformer-kb/`:
```
SCHEMA.md            domain, language policy, tag taxonomy, level template (bootstrapped by ingest)
narrative.md         agreed architecture: hierarchy tree + main threads + core-concept list
sources.md           provenance registry: id, kind (primary|secondary), title, url, version, fetched_at, sha256, verified  (NOT tier — trust is the cross-topic registry's axis, owned by Information Assistant)
materials.md         stage-0 inventory of the raw folder (map-materials)
notes/<topic>.md     stage-1 MECE-restructured notes (clean-notes)
wiki/<slug>.md       stage-2 core-concept pages (llm-wiki-ingest)
index.md, log.md
```
Raw input is **read-only and referenced in place** through `materials.md` with sha256. It is not copied, because the Transformer raw folder is 76 MB of images.

**Hierarchy (vertical classification across pages).** domain → thread → core concept. Each page has a `parent` and a `threads: [...]` field in its frontmatter. Sub-variants are `##` sections inside the parent page, not separate pages. A variant gets its own page only when you agree to it at the gate.

**Concept page template (vertical depth inside a page):**
```markdown
---
title: Attention
parent: transformer           # hierarchy
threads: [attention-lineage]  # horizontal membership
levels: {L1: full, L2: full, L3: partial, L4: stub}   # explicit coverage, never implied
sources: [mat:m007, ext:bahdanau-2014, ext:vaswani-2017]
updated: 2026-10-08
---
## L1 · What it is      problem solved, origin (who/when), use cases, core sub-concepts, diagram
## L2 · Relations       [[links]] with relation type (generalizes / variant-of / prerequisite / contrasts) + core questions
## L3 · Math & code     derivation, shapes, reference implementation (from raw or supplemented)
## L4 · Extensions      adjacent topics, further reading, open questions
## References           [^id] footnotes → sources.md
```

**Provenance rule.** Every paragraph carries a footnote id. A `mat:` id points to a `materials.md` row in the instance — the archive itself is external and written to zero times, and `materials.md` is never written into it. An `ext:` id points to a primary source that was **actually fetched and verified** during the run (paper/arXiv, official docs, canonical repo). Supplemented content is visibly distinct from raw-derived content. If no verified source exists, mark the section `levels: Lx: gap` and do not invent content.

**Granularity rule.** A page is created only for a concept that carries a narrative thread. Fragments fold into the page that owns them. The proposed core-concept list is always shown at the gate.

### B2. Skill rewrites (4 skills, gate every run)

| Stage | Skill | In → Out | Gate |
|---|---|---|---|
| 0 | `map-materials` (rewrite) | raw folder → `materials.md`: per-file/per-H2 rows, stable ids, sha256, key/redundant/peripheral/off-topic, broken-link flags. Writing-specific coupling (pre-write-grill, survey) removed. | confirm off-topic exclusions |
| 1 | `clean-notes` (rewrite, absorbs organize-docs' MECE job) | `materials.md` + raw → `notes/<topic>.md`. Topic understanding across **all** files, MECE outline, dedupe/merge with provenance ids kept, fix image paths. Light supplementation allowed only as marked `ext:` notes. | confirm MECE outline |
| 2 | `llm-wiki-ingest` (rewrite) | notes → wiki. **2a** propose `narrative.md` (hierarchy, threads, core concepts, granularity). **2b** enrich: search for and verify primary sources, register them in `sources.md`. **2c** write pages to the L1–L4 template, then update index/log. Bootstraps `SCHEMA.md` on first run (replaces init). | narrative + concept list (2a); diff summary before writing (2c) |
| — | `llm-wiki-lint` (rewrite) | wiki → report: level coverage matrix, unresolved footnotes, raw sha drift, `narrative.md` ↔ pages consistency, orphans, broken links | none (read-only) |

Reused from the existing skills: clean-notes' dedupe classification (verbatim / near-dup / recurrence), its size-path subagent split, and its CJK-safe prescan. Also llm-wiki-ingest's sha256 snippet, its skip-on-unchanged logic, its contradiction policy, and its subagents-extract-never-write rule.

---

## Phase C: Transformer test run

Input (read-only): `/Users/xhl/Documents/Personal-Projects/Learning/Transformer/Transformer-materials`. It has 19 md files in 3 genres (the CN machine-generated `transformer-note.md`, Shrijeeth's EN lessons, kaushikacharya's shorthand) plus 133 images.
Output: new sibling `Transformer/Transformer-kb/`. `Transformers-wiki-test-1/` is left untouched and kept as the plain-LLM-Wiki baseline for comparison.

1. map-materials → **actual: 41 rows covering 153 files** (the plan's ~30 was a pre-rewrite guess that missed the folder-ancestor row, the per-exception rows and the admin file). Flagged **11 off-topic images** plus a `.gitignore`, **35 occurrences / 33 unique** broken `../../../../images` paths (the plan conflated occurrences with unique targets), and the nested `### Transformer` under Tokenization (row `m005`).
2. clean-notes → **actual: 8 notes** (7 topic + `misc` at 3.4% overflow), all 29 in-scope rows cited, 0 off-topic cited.
3. ingest 2a → **actual: 7 core concepts** (in the 5–8 range) across 4 threads; tokenization → page, MoE → folded `##` section, normalization → page. The narrative shape held.
4. ingest 2b → **actual: 12 rows** (11 primary + 1 secondary). Both DeepLearning.AI pages were correctly excluded (gated, no stable id); `luong-2015`, `su-2021-rope` and `shazeer-2017-moe` were added for concepts the notes only sketched.
5. lint → **actual: 0 critical / 0 high / 0 medium; coverage full 18 · partial 9 · stub 0 · gap 1**.

**Acceptance:**
- The core-concept count is approved by you at the gate. — **PASS** (7 at the 2a gate).
- Every page has all four level sections, each either filled or explicitly marked `gap`. — **PASS** (7/7 pages; one `gap`: `normalization` L4).
- 100% of footnotes resolve, and every `ext:` id has a verified URL. — **PASS** (353 occurrences, 0 unresolved; 12 verified `ext:` rows).
- every `materials.md` row's `sha256` matches its archive file (and a folder row's manifest digest recomputes). — **PASS** (41/41 rows; `m029` digest reproduces).
- A side-by-side read against `Transformers-wiki-test-1` shows that the main narrative survives. — **PASS** (the 119-page granularity failure is fixed).

Findings from the run feed one round of skill revisions before the design is called done.

---

## Phase D: Installation, export and publication (closing phase)

After A2 moves `kb/` and its runtime surface to Information Assistant, the store's P2/P3 runtime verification travels with it. What survives in this repository is the skill surface and the publication of the repositioned product. The kb-interop items of the retired P2–P5 plan (KB installs with tools alone, with no information package; isolated-environment package testing) belong to Information Assistant and are not repeated here. These are its live, AKB-side items.

**D1. Skill installation and export** → verify: Skills Manager lists the four KB skills with their retained IDs, presets and deployments, and a fresh export reproduces the discovery links from `catalog/` — **done 2026-10-09**
- [x] Refresh the migrated installed skills through Skills Manager, retaining IDs, presets and deployments. Do not edit the manager database or any global skill copy by hand.
- [x] Regenerate discovery links with `uv run python scripts/export-skills.py` and confirm they match `catalog/skill-set.json` and the `SKILL.md` directories on disk.
- [x] Skills Manager reassociation: the four entries now track the committed public repository as a git source.
- [x] **Writing Assistant: done.** Its repository got its first commit and a private remote (`XinheLIU/writing-assistant`), then all **23** of its entries — including `archive-materials` and `llm-wiki-book` — were re-pointed from the pre-migration `learning-os-standalone` local copies to the repository as a git source. Preset membership and deployments unchanged; 3 dangling references left by the repositioning (`archive-materials`' `survey.md` archive lookup, its `organize-docs` handoffs, `llm-wiki-book`'s retired `llm-wiki-init`) were repaired in Writing Assistant, together with two broken links and a missing discovery symlink.
- [ ] **Deferred, gated on the owning repository's own migration:** the manager CLI can re-point a *git* source only, and re-pointing fetches the **remote** revision — so an entry cannot be refreshed before its repository has committed the moved layout. Two entries remain:
  - Learning OS — `recall` (`skills/learning/recall`) and `survey`. Learning OS has commits and a remote, but its P0/P1 migration (130 uncommitted changes) is not committed, and `skills/planning/survey` does not exist at its remote revision. Re-pointing now would either fail or pull pre-migration content, so it waits on that repository committing its own migration.
  - Information Assistant — `curate-sources` (`skills/sources/curate-sources`). That repository still has no commits at all.
  Once each owner commits, regenerate its standalone export and re-point through the manager the same way.

**D2. Publication** → verify: no published description presents the retired collector or the admission store as current — **done 2026-10-09**
- [x] Correct stale LangGraph / collector descriptions only as part of the website/Profile publication change, and link actual evidence rather than asserting behaviour.
- [x] Commit, remote repository creation, push, pin advancement and deployment require an explicit request. The request was given for this phase.

### D1 evidence (2026-10-09)

The public repository was committed and pushed first (`19dc1b7`), because the manager resolves a git source at its remote revision.

| Installed entry | id retained | source before → after | preset | deployed |
| :-- | :-- | :-- | :-- | :-- |
| `map-materials` | `76826e28-a2ba-4887-8d7d-7b61713197fb` | `local-sources/learning-os-standalone/…` → `git XinheLIU/Agentic-Knowledge-Bank` `skills/knowledge/map-materials` | Knowledge & Learning | none (unchanged) |
| `clean-notes` | `00e5a66d-7fa7-4f59-a2ba-55f5e3482d13` | same → `…/skills/knowledge/clean-notes` | Knowledge & Learning | none |
| `llm-wiki-ingest` | `af8cdcaa-4532-4d9e-8616-64db543a6806` | `GitHub/agent-projects/learning-os/…` (path no longer exists) → `…/skills/knowledge/llm-wiki-ingest` | Knowledge & Learning | none |
| `llm-wiki-lint` | `5b5fba4b-7104-4775-a766-2051402280a6` | `GitHub/agent-projects/learning-os/…` → `…/skills/knowledge/llm-wiki-lint` | Knowledge & Learning | none |

Writing Assistant (23 entries, all re-pointed `local → git` at `https://github.com/XinheLIU/writing-assistant`, revision `f043cf4`): `add-pedagogy`, `archive-materials`, `assess-readiness`, `book-diagrams`, `book-translator`, `build-skeleton`, `create-tech-slides`, `define-audience`, `develop-argument`, `develop-examples`, `edit-targeted`, `elevate-draft`, `frame`, `grill`, `insert-inline-images`, `llm-wiki-book`, `outcome-design`, `package-chapter`, `pre-write-grill`, `review-draft`, `sequence-design`, `snapshot-writing`, `write-content`.

- All four were re-pointed in place with `skills set-source … --git-url https://github.com/XinheLIU/Agentic-Knowledge-Bank --subpath skills/knowledge/<name> --branch main --force`; the manager resolved revision `19dc1b7` and reported `content_changed: true`. Each installed `SKILL.md` is byte-identical to the repository's, and `skills check` reports `up_to_date`.
- `llm-wiki-init` and `organize-docs` were **removed** from the library (no deployments existed); the library went 480 → 478 entries and the *Knowledge & Learning* preset 27 → 25.
- The four KB skills were then **deployed** to `pi`, `claude_code` and `codex` (the three hosts the library's other actively used skills target), each as a symlink into the central library. `deployed_to` is now `[claude_code, codex, pi]` for all four; the writing-era state was empty, so this is an addition, not a retained relationship.
- The library CLI supports re-pointing **git** sources only; `skills install` on an existing name creates a suffixed duplicate, which the migration rules forbid, so no local export was re-installed.

```text
$ uv run --no-sync python scripts/export-skills.py --output /tmp/akb-d1-export
Exported 4 self-contained skills to /private/tmp/akb-d1-export

catalog      clean-notes llm-wiki-ingest llm-wiki-lint map-materials
skills/      clean-notes llm-wiki-ingest llm-wiki-lint map-materials
.claude-plugin/skills/  clean-notes llm-wiki-ingest llm-wiki-lint map-materials  (4/4 symlinks resolve)
export dirs  clean-notes llm-wiki-ingest llm-wiki-lint map-materials  (0 broken links after rewriting)
```

### D2 evidence (2026-10-09)

The only published description naming this product was the GitHub Profile README line in `publishing/github-profile` (the site source carried none). It now reads as a provenance-tracked concept wiki and links `docs/knowledge-model.md` as its evidence. `pyproject.toml`'s harness description was the other stale string ("AI 知识库 — 自动化技术情报收集与分析系统", the retired collector) and was replaced.

---

## Out of scope / noted
- Step 2 (compounding): only the draft extraction in A3.
- `/Users/xhl/GitHub/CLAUDE.md` routing table and `skills/agent-skills/catalog/sources.json` still use the pre-`Learning-Products/` paths. They are mentioned here, not edited.
- Skills-manager reassociation is complete for this repository and Writing Assistant; the two outstanding entries belong to Learning OS (`recall`, `survey`) and Information Assistant (`curate-sources`) and are gated on those repositories committing their own migrations — see D1. Not this effort's to force.
