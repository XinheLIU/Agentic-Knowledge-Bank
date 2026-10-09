# Architecture and boundaries

Last updated: 2026-10-09

## Domain model

The meaning of every term used here is frozen in the [knowledge model](knowledge-model.md), with [CONTEXT.md](../CONTEXT.md) as its glossary. Change the model there first, then in the four skills. This file records structure and ownership only.

## The product pipeline

A knowledge instance is built by three stages, each with exactly one skill owner:

```
archive (external, read-only)
   │
   │  map-materials          stage 0 — inventory
   ▼
materials.md                  rows: one per file or `##` section
   │
   │  clean-notes            stage 1 — evidence
   ▼
notes/<topic>.md              MECE clusters, provenance ids intact
   │
   │  llm-wiki-ingest        stage 2 — presentation
   ▼
wiki/<slug>.md                L1–L4 concept pages, per-paragraph footnotes
```

`llm-wiki-lint` is read-only over the result: level coverage, unresolved footnotes, archive sha drift, `narrative.md` ↔ pages consistency, `index.md` completeness, orphans and broken links. Its asset audit covers both notes and pages; note fidelity and deduplication remain stage 1's responsibility.

**Evidence and presentation are different layers on purpose.** A note reports what the material says — nothing added, improved or judged. A page explains a concept to a reader. Collapsing them loses either traceability or readability.

**The archive is not a stage.** It is an external folder referenced by absolute path and never written to. `materials.md` lives in the instance, not the archive.

## Instance layout

One canonical production instance per domain, external to this repository; explicitly authorized
isolated acceptance instances are not additional production authorities:

```
<domain>-kb/
├── SCHEMA.md          conventions: domain, language, tags, level template, update policy
├── narrative.md       the agreed architecture: hierarchy, threads, core-concept list
├── sources.md         provenance registry of verified sources (primary/secondary)
├── materials.md       stage 0: the archive inventory, one row per material
├── notes/<topic>.md   stage 1: MECE evidence notes
├── wiki/<slug>.md     stage 2: concept pages
├── index.md           one entry per page
└── log.md             append-only action log
```

The instance root is an explicit parameter (`$KB_PATH`), never a default. The archive path is recorded in `materials.md`'s header as an `archive: <abs-path>` line.

## Provenance

Every paragraph carries at least one provenance id:

- `mat:m007` — a row in `materials.md`
- `ext:vaswani-2017` — a verified row in `sources.md`

`ext:` rows record a real URL, a `fetched_at` date, a `sha256` and the exact version read. Where no verified source exists, the level is marked `gap` — content is never invented. A page's `sources:` frontmatter is a two-way audit index over its footnotes.

## Boundaries

| Product | Relation |
|---|---|
| **Information Assistant** | Upstream. Source discovery; owns the cross-topic source registry and the trust axis. Its outputs can become raw input here. |
| **Learning OS** | Downstream. Reads wiki pages as study material; owns attempts and mastery. **Never written to by AKB.** |
| **Writing Assistant** | Downstream. Takes wiki pages and `materials.md` as sourced material; owns `archive-materials` and the `used-in` column. |
| **Synapse** | Derived cross-source index over published wiki pages. |

The write boundaries are per file and per column. Cross-product calls use explicit package/CLI interfaces or named artifacts. Do not reach into another product's private database, mutate another product's learner state, or depend on a sibling checkout at runtime.

## Shared architecture

Host → domain Plugin → domain skills/workflows/state → explicit user data.

A **Skill** owns task instructions; a **Tool** owns an independently callable operation; **MCP** exposes either kind of capability. A product plugin packages its domain capability; it does not become another agent runtime.

## Handoffs

- **From Information Assistant:** source registries and collected provider payloads. Its outputs can become raw input in the archive.
- **To Learning OS:** published wiki pages, read-only. Learning OS owns the follow-through.
- **To Writing Assistant:** wiki pages and `materials.md`, used as sourced material. `archive-materials` writes only the `used-in` column.
- **To Synapse:** published wiki pages, indexed as a derived cross-source layer.

## Current state

The knowledge model and the four skill contracts are the design. The repositioning — including the retirement of the previous runtime, which moves to Information Assistant — is tracked in the [wiki-repositioning plan](exec-plans/wiki-repositioning.md). Runtime behavior has not been re-verified under the new model.
