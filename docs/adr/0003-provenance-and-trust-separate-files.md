# 0003 — Instance provenance and cross-topic trust stay separate files

> Last updated: 2026-10-08

Status: Accepted — 2026-10-08

The registries this decides are specified in [docs/knowledge-model.md](../knowledge-model.md); this record does not restate their columns. It records *why* two things that are both called "sources" are deliberately not merged.

## Context

The knowledge model has two registries that both answer a question about a source, and both are informally called "sources":

1. **Instance provenance** — `sources.md`, scoped to one topic's instance. It records what a claim in *this* instance is traceable to: `id`, `kind` (`primary` / `secondary`), `title`, `url`, `version`, `fetched_at`, `sha256`, `verified`. It is written by `llm-wiki-ingest` at stage 2b, when a primary source is actually fetched and verified.
2. **Cross-topic trust** — the `sources/<domain>.md` registry, owned by **Information Assistant**. It records how much a source's word is worth across every topic: tier, verdicts, reputation over time.

They share an identity space, so they look like duplication and merging looks like cleanup — one file, one set of rows, one place to look. The plan for the repositioning did in fact merge them: it put `tier` inside the instance registry.

Recipe for confusion: the two measure different things. Provenance answers "*where did this specific claim come from, and can I re-fetch and re-check it?*" Trust answers "*when this source speaks, how much should I believe it across all topics?*" A source can be a verified, exactly-versioned provenance anchor in one instance and a low-tier source in the cross-topic registry, with no contradiction.

A second axis sits alongside: `kind` (`primary` / `secondary`) is **not** trust. It is an intrinsic property of a work relative to the claim — the work itself (paper, official docs, canonical repo) versus an exposition of it. A secondary source is fine as an `ext:` anchor for *explaining*; it can never carry a priority claim ("first introduced"). That distinction belongs to the claim's provenance and is not a rating of the source.

## Decision

**Keep the two axes in two files, joined by an id.**

- The instance `sources.md` owns **provenance only** — per-fetched-source identity, version, retrieval date and body hash, plus `kind: primary | secondary`. It makes a claim auditable inside the instance.
- The cross-topic `sources/<domain>.md` registry, owned by Information Assistant, owns **trust only** — tier and verdicts. It is not copied into instances.
- `materials.md`'s `source-id` column is the **join key** between an instance material and the cross-topic registry; an unregistered material carries `—`.
- Provenance is mandatory for a cited claim; trust is not required to cite. An `ext:` id needs a verified row in the instance `sources.md` (url, version, `fetched_at`, `sha256`); it does not need a tier.

## Alternatives considered

1. **Merge into a single registry.** *Rejected.* One file would carry two ownerships, two lifetimes and two questions. Trust is cross-topic and maintained by Information Assistant as it learns; provenance is per-instance and frozen at fetch time. A merge either drags the whole cross-topic reputation table into every topic's instance, or makes the instance depend on an external file for its own traceability.
2. **Keep the plan's original: put `tier` in the instance `sources.md`.** *Rejected (this reversed the plan).* A single topic's instance has no basis for a *cross-topic* judgement, and trust is Information Assistant's to own. Per-instance tiers would duplicate and drift from the global registry, and updating a source's standing would mean editing every instance that cites it.
3. **Keep provenance in the cross-topic registry too, one registry total.** *Rejected.* The instance must stay self-describing about where its own claims came from; outsourcing provenance makes the instance un-lintable on its own and couples a claim's audit trail to another product's state.
4. **Let `kind` carry the trust judgement** (treat `primary` as high trust, `secondary` as low). *Rejected.* It conflates "is this the work itself?" with "how good is this source?". A well-regarded textbook is high trust but still secondary; a canonical repo is primary regardless of tier.

## Consequences

**Positive**

- Each file has one owner and one question, so each can change for its own reason: trust improves centrally as Information Assistant learns; a claim's provenance is frozen in the instance that made it.
- Version pinning and `sha256` live where they are checked (the instance), while tier lives where it is curated (Information Assistant) — no cross-contamination, no duplicated rows.
- The `kind` axis keeps the priority-claim rule mechanical: only `primary` can support "first introduced"; a claim resting on a `secondary` source is visibly weaker and pairs with the optional `confidence` field.
- Provenance survives instance export and re-import unchanged; trust changes never rewrite instance files.

**Negative / to manage**

- **An id join to maintain.** `materials.md.source-id` must resolve in the cross-topic registry. A renamed registry id silently breaks the join — a new failure mode that needs a lint check or an Information Assistant follow-up (see ticket **Decide `materials.md` ownership across AKB and Writing Assistant**).
- **Two files to keep in step.** The same source appears in many instances and once in the registry; readers must know which file answers which question.
- **Two things named "sources".** The vocabulary distinguishes them (the instance `sources.md` registry vs the cross-topic source registry), but the shared word remains a documentation burden and a standing invitation to re-merge.
- **A cross-product dependency.** The instance points into a registry owned by another product; the join is a live interface between AKB and Information Assistant, not an internal detail.

## Status

Accepted — 2026-10-08. Reverses the plan's placement of `tier` in the instance registry; preserves the cross-topic trust axis with Information Assistant while the instance keeps the provenance axis.
