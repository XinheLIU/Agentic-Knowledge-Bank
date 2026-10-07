# Memory routing

Last updated: 2026-10-04

## Current ownership

This repository owns knowledge assets, admission, storage, knowledge-maintenance skills, UI and MCP. Information orchestration/digests moved to Information Assistant; provider tooling moved to agent-tools.

- Current rules: [AGENTS](../../AGENTS.md) and [domain invariants](../domain-invariants.md).
- Test harness: `tests/conftest.py` pins the `agent-tools` profile constants to this repository's structural fixtures (`tests/fixtures/horizon-profiles/`), because the canonical profile set lives with Information Assistant and the library binds those constants at import time. Sibling-repository failures are recorded in [sibling-repo-failures.md](../sibling-repo-failures.md).
- Horizon-run surface retired (2026-10-04): the KB-side provider shims, the `scripts/production_run.py` / `scripts/setup_horizon.py` launchers, `kb.ingest.ingest_horizon_run`, the `kb.cli` information-command forwarding and the run/digest summaries are removed. Provider plumbing belongs to agent-tools; orchestration, scheduling and digests belong to Information Assistant; KB only admits a completed payload via `kb.ingest.ingest_horizon_payload`.
- Current architecture: [ownership and interfaces](../architecture.md).
- Pending execution: [P2–P5](../exec-plans/workspace-refactor.md).
- Prior Horizon effort: `.scratch/horizon-kb-design/` (including its `state.md`) remains local historical working evidence. Its original paths and completed tickets are not new acceptance evidence.
- Historical technical design: [Horizon cutover](../product/ai-kb/design.md).

Do not rewrite user-authored TODOs or resurrect retired LangGraph workflows. The current migration has not run behavioral checks.
