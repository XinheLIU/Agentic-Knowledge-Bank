# Memory routing

Last updated: 2026-10-08

## Current ownership

This repository owns the **knowledge model** and the four concept-wiki skills: `map-materials` (inventory), `clean-notes` (MECE evidence notes), `llm-wiki-ingest` (concept pages) and `llm-wiki-lint` (audit).

It does not own source discovery or the cross-topic source registry (Information Assistant), learner state / attempts / mastery (Learning OS), or writing output (Writing Assistant, which also owns `archive-materials`).

- Domain model: [knowledge model](../knowledge-model.md); glossary: [CONTEXT.md](../../CONTEXT.md).
- Current rules: [AGENTS](../../AGENTS.md) and [domain invariants](../domain-invariants.md).
- Architecture and boundaries: [ownership and interfaces](../architecture.md).
- Current plan: [wiki repositioning](../exec-plans/wiki-repositioning.md).

A knowledge instance is external and read-only over its archive; no instance data is a fixture. The previous runtime's harness, fixtures and docs (`docs/product/ai-kb/`, `docs/adr/0001-*`) travel to Information Assistant with the code — see the plan.

## Retired work

The previous provider/runtime surface and its test harness left this repository with the runtime; provider plumbing belongs to agent-tools and orchestration, scheduling and digests belong to Information Assistant. Do not reconstruct the retired LangGraph workflows, prompts or hooks, and do not rewrite user-authored TODOs.

The repositioning has not completed its Transformer acceptance run, so runtime behavior under the new model is not yet verified.
