# Agentic Knowledge Bank

Last updated: 2026-10-09

Agentic Knowledge Bank builds **provenance-tracked concept wikis**. A *knowledge instance* is the durable output: one topic's understanding, structured by narrative, deep enough inside each concept to be studied from, and traceable paragraph by paragraph to the material or the primary source a claim came from.

The domain model is frozen in [docs/knowledge-model.md](docs/knowledge-model.md). [CONTEXT.md](CONTEXT.md) is its glossary.

## The two purposes

1. **Cognitive asset accumulation** — a wiki derived from raw material where every claim traces to a material row or to an authoritative primary source.
2. **Cognitive compounding** — deferred to a later design; only its draft material is kept.

## Pipeline

```
archive          ──map-materials──▶  materials.md  ──clean-notes──▶  notes/  ──llm-wiki-ingest──▶  wiki/
(read-only)                           stage 0: inventory             stage 1: evidence             stage 2: presentation
```

The stages do different jobs on purpose, and no stage is skipped:

- **Inventory** (`map-materials`) — one row per material: path, kind, role, sha256, concepts, flags. Externally the archive is the source of truth; the inventory is written into the instance.
- **Notes** (`clean-notes`) — the material of a topic merged, deduplicated and clustered with its provenance ids intact. Notes are *evidence*: nothing is added, improved or judged.
- **Wiki** (`llm-wiki-ingest`) — concept pages on the L1–L4 depth template, each paragraph carrying a footnote. `llm-wiki-lint` audits level coverage, unresolved footnotes, sha drift and consistency.

The **archive** is an external folder accumulated by you, referenced by absolute path and **never written to**. `materials.md`, `notes/` and `wiki/` live in the instance; instance data is external to this repository and is never packaged.

## Relationships

| Product | Relation to AKB |
|---|---|
| **Information Assistant** | Upstream. Discovers sources, owns the cross-topic source registry and the trust axis. Its outputs can become raw input here. |
| **Learning OS** | Downstream. Reads wiki pages as study material and owns attempts and mastery. Never written to by AKB. |
| **Writing Assistant** | Downstream. Takes wiki pages and `materials.md` as sourced material, and owns `archive-materials` and the `used-in` column. |
| **Synapse** | Derived cross-source index over published wiki pages. |

## Entry points

- [Architecture and boundaries](docs/architecture.md)
- [Knowledge model](docs/knowledge-model.md)
- [Domain invariants](docs/domain-invariants.md)
- [Repositioning plan](docs/exec-plans/wiki-repositioning.md)
- [Agent instructions](AGENTS.md)
- [Skill catalog](catalog/skill-set.json)

## Status

The knowledge model is frozen and the four skills are rewritten against it. The Transformer run in [the plan](docs/exec-plans/wiki-repositioning.md) Phase C **passed** (2026-10-09): every footnote resolves, every `ext:` id has a verified URL, and every `materials.md` sha256 matches the archive. Phases A–C are done; Phase D (skills installation/export and publication) is pending. Do not infer runtime behaviour from structural checks.
