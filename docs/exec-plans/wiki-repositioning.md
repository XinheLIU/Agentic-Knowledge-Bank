# Plan: Re-position Agentic-Knowledge-Bank as a provenance-tracked concept wiki

Last updated: 2026-10-09

Status: **Phases A–C done; Phase D pending** (updated 2026-10-09 by ticket 18). A1–A4 landed; B1 is frozen in `docs/knowledge-model.md` and B2 in the four `skills/knowledge/*/SKILL.md`; the Phase C Transformer run passed every structural acceptance criterion (ticket 17) and its findings fed the skill/model revisions in ticket 18. D1 and D2 (installation, export, publication) remain open. No git write operations were performed.

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

**D1. Skill installation and export** → verify: Skills Manager lists the four KB skills with their retained IDs, presets and deployments, and a fresh export reproduces the discovery links from `catalog/`
- [ ] Refresh the migrated installed skills through Skills Manager, retaining IDs, presets and deployments. Do not edit the manager database or any global skill copy by hand.
- [ ] Regenerate discovery links with `uv run python scripts/export-skills.py` and confirm they match `catalog/skill-set.json` and the `SKILL.md` directories on disk.
- [ ] Skills Manager `origin.json` reassociation stays pending until this repository has committed history; commits require an explicit request.

**D2. Publication** → verify: no published description presents the retired collector or the admission store as current
- [ ] Correct stale LangGraph / collector descriptions only as part of the website/Profile publication change, and link actual evidence rather than asserting behaviour.
- [ ] Commit, remote repository creation, push, pin advancement and deployment require an explicit request.

---

## Out of scope / noted
- Step 2 (compounding): only the draft extraction in A3.
- `/Users/xhl/GitHub/CLAUDE.md` routing table and `skills/agent-skills/catalog/sources.json` still use the pre-`Learning-Products/` paths. They are mentioned here, not edited.
- Skills-manager `origin.json` reassociation stays in P2.
