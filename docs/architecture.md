# Ownership and interfaces

Last updated: 2026-10-04

## Product

Maintain traceable knowledge assets and preserve their provenance.

`kb/` owns asset identity, admission, ingest, SQLite storage and read APIs. `skills/knowledge/` owns material mapping, note cleanup, document organization and wiki maintenance. The existing UI and MCP remain in this repository.

Information Assistant owns source discovery, pipeline scheduling and digests. Synapse owns derived cross-source retrieval indexes. The canonical store and source content stay here or in the explicitly configured private instance.

## Shared architecture

Host → domain Plugin → domain skills/workflows/state → business API and independent tools → explicit user data.

A Skill owns task instructions; a Tool owns an independently callable operation; MCP exposes either kind of capability. A product plugin packages its domain capability. It does not become another agent runtime.

## Handoffs

Information Assistant publishes source registries and collected provider payloads. Knowledge Assistant admits and maintains assets with provenance. Learning OS consumes selected material and owns attempts and mastery evidence. Writing Assistant consumes agreed material and writes only into the content owner's workspace. Synapse indexes published sources and produces source-backed recall; its indexes are derived.

Cross-product calls use explicit package/CLI interfaces or named artifacts. Do not reach into another product's private database, mutate another product's learner state, or depend on a sibling checkout at runtime.

## Compatibility

Existing repository names and published versions remain. The local split is unreleased. KB imports the `agent-tools` Horizon contract directly, so no KB-side provider shim owns a second implementation, and KB exposes no collection entry point: the run/ingest/digest commands live in Information Assistant (`information-run`, `information-assistant`). KB admits a completed provider payload through `kb.ingest.ingest_horizon_payload`; the payload is the named artifact and carries its own run identity — including the pinned provider revision it was produced against — so KB never infers or substitutes a reference.

New local package names are `xinhe-agent-tools` (`agent_tools`) and `information-assistant` (`information_assistant`). KB keeps `ai-kb` (`kb`). Information depends on KB and tools; KB depends only on tools. Third-party dependencies remain within the existing stack.
