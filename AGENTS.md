# Agent instructions

Last updated: 2026-10-04

## Product boundary

`kb/` owns asset identity, admission, ingest, SQLite storage and read APIs. `skills/knowledge/` owns material mapping, note cleanup, document organization and wiki maintenance. The existing UI and MCP remain in this repository.

Information Assistant owns source discovery, pipeline scheduling and digests. Synapse owns derived cross-source retrieval indexes. The canonical store and source content stay here or in the explicitly configured private instance.

## Source and data

- Keep one canonical implementation of each skill, script and domain rule.
- Read [architecture](docs/architecture.md) and the [execution plan](docs/exec-plans/workspace-refactor.md) before changing ownership or interfaces.
- Personal state is external to this repository. Use explicit instance configuration; never package actual learner, household or private knowledge data.
- The shared discovery frontend is owned by `../../skills/agent-skills`; this is a development location, not a runtime dependency.
- Skill changes update `catalog/skill-set.json`; regenerate discovery links and exports instead of editing them.
- Update `Last updated` near the top of every modified Markdown file.
- Preserve existing local changes. Do not commit, push, deploy or advance submodule pins without an explicit request.

## Current acceptance boundary

The 2026-10-04 request authorizes source migration and static integrity checks. Runtime checks, service startup, external collection, delivery, host installation and learning experiments remain P2/P3 work. Never mark them passed from structural evidence.

## Domain rules

[Domain invariants](docs/domain-invariants.md) remain authoritative after extraction.
