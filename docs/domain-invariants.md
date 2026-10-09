# Domain invariants

Last updated: 2026-10-08

Source: [docs/knowledge-model.md](knowledge-model.md) § Invariants. These are the invariants the four skills and the instance layout must satisfy; change the model first, then this mirror.

1. **The archive is read-only.** Nothing is ever written into it — no map, no hash refresh, no rename, no reorganisation.
2. **Every claim traces.** Each paragraph carries a provenance id resolving to a `materials.md` row or a verified `sources.md` row.
3. **No verified source → `gap`.** Content is never invented, and a gap is always explicit.
4. **Provenance survives every stage.** A note keeps its materials' `mat:` ids through dedupe and merge; a page keeps its notes' provenance through writing.
5. **A page exists only for a threaded concept** that can fill L1 and L2. Everything else folds.
6. **One instance per domain**, external to this repository. Instance data is never packaged, never a fixture.
7. **One canonical implementation per skill.** A stage has exactly one owner.
8. **AKB never writes learner state.** Attempts, mastery and evidence belong to Learning OS.
