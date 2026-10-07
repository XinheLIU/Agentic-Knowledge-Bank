# Knowledge Assistant / Agentic Knowledge Bank

Last updated: 2026-10-04

Maintain traceable knowledge assets and preserve their provenance.

## Current state

P0/P1 ownership and source migration is complete in the local worktree. The code, skills and references have been separated; runtime, independent plugin installation and end-to-end behavior have **not** been tested in this round. New repositories have no published release.

## Ownership

`kb/` owns asset identity, admission, ingest, SQLite storage and read APIs. `skills/knowledge/` owns material mapping, note cleanup, document organization and wiki maintenance. The existing UI and MCP remain in this repository.

Information Assistant owns source discovery, pipeline scheduling and digests. Synapse owns derived cross-source retrieval indexes. The canonical store and source content stay here or in the explicitly configured private instance.

## Entry points

- [Skill catalog](catalog/skill-set.json)
- [Product metadata](catalog/product.json)
- [Architecture and handoffs](docs/architecture.md)
- [P2–P5 execution plan](docs/exec-plans/workspace-refactor.md)
- [Agent instructions](AGENTS.md)

## Delivery

The domain harness is delivered as a host plugin. Claude Code is the first verification target; other hosts require their own acceptance evidence. `.claude-plugin/` contains the local source descriptor and generated skill discovery links; this is not a claim that independent installation has passed.

Source definitions live under `skills/`. Discovery views and exported packages are derived. `scripts/export-skills.py` uses the separately installed `agent-tools` exporter. Skills Manager owns the central installation library and host deployment links; do not copy implementations into global agent directories.

## Development

Use existing Python/Node tooling and isolated environments. Do not commit, push, publish or deploy without an explicit request. Migration static checks are recorded in the workspace report; run the remaining behavioral checks during P2/P3.
