# 0002 — The archive is external and read-only; the wiki is a derived view

> Last updated: 2026-10-08

Status: Accepted — 2026-10-08

The knowledge model this decides is frozen in [docs/knowledge-model.md](../knowledge-model.md); this record does not restate it. It records *why* the layout was chosen, because the layout is hard to reverse and the obvious alternative is the opposite one.

## Context

Agentic-Knowledge-Bank builds provenance-tracked concept wikis. A wiki page must trace every paragraph back to the material a claim came from, and the value of the trace depends on the material being the *original* — not a rewritten, re-hashed or re-organised copy.

The material for a topic is large and heterogeneous. The Transformer archive is the concrete case: 19 Markdown files across three genres, 133 images, 156 files, about 76 MB. It is unversioned, cloud-synced, and accumulated over time — it is "what you collected, not what you wrote" (`CONTEXT.md`).

The previous generation kept raw material *inside* the knowledge tree: `raw/` was a stage directory, each raw file carried `source_url`, `ingested` and `sha256` frontmatter, and `llm-wiki-ingest` wrote a refreshed `sha256` back into the raw file on drift. That made the instance nominally self-contained, but it also made the source of truth a mutable part of the pipeline, and the copy in the tree was the thing being edited.

The obvious design, therefore, is the one that was rejected: copy or stage the material inside the instance so the instance is self-contained, portable, and path-independent. This ADR records why we deliberately gave that up.

## Decision

**The archive is an external, read-only folder, referenced in place; the notes and wiki are derived views over it.**

- The instance (`<domain>-kb/`, root path `$KB_PATH`, explicit, never defaulted) holds `SCHEMA.md`, `narrative.md`, `sources.md`, `materials.md`, `notes/`, `wiki/`, `index.md`, `log.md` — and **no copy of the material**.
- `materials.md` — the stage-0 inventory — lives **in the instance**, one row per material, with the archive-relative `path` and a `sha256` of the file as read. Its header carries `archive: <abs-path>`, so the instance knows its own archive.
- No skill writes into the archive: not a map, not a hash refresh, not a rename, not a `.DS_Store` sweep. `map-materials` proves it mechanically by asserting no archive file is newer than the session start.
- Provenance is a per-paragraph id — `mat:m007` for an inventory row, `ext:<slug>` for a verified fetched source. Ids point *at* the archive and the registry; they never point at instance-local copies.

The archive is written to **zero** times. Moving `materials.md` out of the archive (and into the instance) is what makes that literal rather than aspirational.

## Alternatives considered

1. **Copy the material into the instance** (e.g. `<domain>-kb/archive/` or a `raw/` directory). *Rejected.* It buys self-containment and path-independence, but it duplicates 76 MB, creates a **second source of truth that can drift** from the original, and turns the copy into the thing that gets edited — which is exactly the weakness of the old `raw/` contract. It also muddies the hash anchor: with two copies, "which is the original?" is a question again.
2. **Reference in place but write metadata back into the archive** (the old behaviour: `sha256` / `ingested` / `source_url` in raw frontmatter, hash refresh on drift, `learning/<slug>/survey.md` stub). *Rejected.* It keeps everything in one tree, but it mutates the source of truth, makes "read-only" unverifiable, and crosses the product boundary `AGENTS.md` forbids (writing learner state).
3. **Symlink the archive into the instance.** *Rejected.* It keeps a single content copy while offering a self-contained-looking path, but symlinks break on move and across machines, their cloud-sync behaviour is undefined, and the instance still appears to own a directory it does not.
4. **Version the archive inside the repository.** *Rejected.* The material is large, unversioned and cloud-synced by design; versioning 76 MB of images is the wrong tool, and it would make the repo a mirror of personal state the repository is explicitly forbidden to package.

## Consequences

**Positive**

- The archive is the untouched original, so a `mat:` footnote resolves to an immutable artifact and its `sha256` is a meaningful drift anchor rather than a checksum of a copy.
- Read-only stops being a promise and becomes a checkable property: nothing in the archive may be newer than the session start.
- The instance stays small and versionable; raw size never leaks into the repo, the instance, or an export.
- There is exactly one source of truth, so there is no copy to reconcile and no "which one is canonical" ambiguity.

**Negative / to manage**

- **The instance is not self-contained.** It is unusable without its archive: resolving `mat:` ids, drift checks and lint all read files the instance does not own, so archive availability (and permissions) becomes a runtime dependency. This is the deliberate trade of portability for provenance strength.
- The `archive: <abs-path>` header line is machine-specific; the relative `path` column survives a move, but the header must be updated and every hash re-checked if the archive relocates.
- Backup and retention now cover two artifacts whose correspondence must be maintained.
- A published page depends on material outside the published tree; a reader of the wiki alone cannot resolve its footnotes without the archive.

## Status

Accepted — 2026-10-08. Supersedes the old in-tree `raw/` contract (raw frontmatter carrying `sha256` / `ingested` / `source_url`, and ingest writing the hash back). ADR `0001` describes the retiring Information Assistant admission pipeline and moves with it; this is the first ADR of the repositioned repository.
