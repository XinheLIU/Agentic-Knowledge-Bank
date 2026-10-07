# 0001 — Knowledge assets are identified by radar-minted immutable IDs

> Last updated: 2026-09-13

A fetched candidate, its admission decisions, and its persisted asset all need one identity that survives fetch, rejection, persistence, retrieval, and export; the legacy pipeline broke this by minting IDs at two points (G1/G2). We therefore adopt a single rule: the Horizon adapter's mapper mints `<radar>:<opaque Horizon id>` exactly once, every later stage (store, admission, retrieval, MCP, UI, digest, export) uses that string verbatim, and no stage renames, re-derives, or re-slugs it. The URL unique index collapses same-document-different-ID candidates at admission (`DUPLICATE_URL`, with a `duplicate_of` pointer), while same-story-different-URL is admitted separately and linked by fingerprint in the reserved `edges` table rather than dropped. Status: Accepted.
