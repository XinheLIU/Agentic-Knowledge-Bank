# Agent instructions

Last updated: 2026-10-09

## Product boundary

This repository owns the **knowledge model** and the four concept-wiki skills: `map-materials` (stage 0 inventory), `clean-notes` (stage 1 MECE evidence notes), `llm-wiki-ingest` (stage 2 concept pages) and `llm-wiki-lint` (audit). The model is frozen in [docs/knowledge-model.md](docs/knowledge-model.md); [CONTEXT.md](CONTEXT.md) is its glossary.

A knowledge instance is one topic's folder, external to this repository: `SCHEMA.md`, `narrative.md`, `sources.md`, `materials.md`, `notes/`, `wiki/`, `index.md`, `log.md`. The archive it inventories is external and **read-only**. Instance data is never packaged and never a fixture.

Information Assistant is upstream (source discovery, cross-topic source registry and trust). Learning OS and Writing Assistant are downstream readers; Synapse derives a cross-source index. This repository never writes learner state.

## Source and data

- Keep one canonical implementation of each skill, script and domain rule. A stage has exactly one owner.
- The knowledge model is the single source the four skills cite: change it there first, then in the skills.
- Read [architecture](docs/architecture.md) and the [execution plan](docs/exec-plans/wiki-repositioning.md) before changing ownership or interfaces.
- Instance data is external to this repository. Use explicit instance configuration; never package actual learner, household or private knowledge data.
- The shared discovery frontend is owned by `../../skills/agent-skills`; this is a development location, not a runtime dependency.
- Skill changes update `catalog/skill-set.json`; regenerate discovery links and exports instead of editing them.
- Update `Last updated` near the top of every modified Markdown file.
- Preserve existing local changes. Do not commit, push, deploy or advance submodule pins without an explicit request.

## Current acceptance boundary

The 2026-10-08 repositioning authorizes the knowledge model, the four skill rewrites and the Transformer run. The structural checks — footnote resolution, `ext:` verification, `materials.md` sha256 matching the archive — **passed on 2026-10-09** (ticket 17); runtime checks, service startup and delivery remain pending, and must never be marked passed from structural evidence.

## Domain rules

[Domain invariants](docs/domain-invariants.md) are authoritative and mirror `docs/knowledge-model.md` § Invariants.
