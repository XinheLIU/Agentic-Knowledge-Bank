# Knowledge Assistant: P2–P5 execution plan

Last updated: 2026-10-04

Status: pending execution. P0/P1 source relocation is recorded centrally; no runtime or behavioral pass is asserted.

## P2 — Installation and interfaces

- [ ] Create a fresh isolated environment from the updated `uv.lock`; moved `.venv` executables and editable source pointers are not portable. Test built packages without the local uv source overrides before release.

- [ ] Refresh the migrated installed skills through Skills Manager using `docs/installed-skill-migration.md`; retain IDs, presets and deployments. Do not edit the manager database or global skill copies.

- [ ] Verify KB installs with tools alone and no information package. Check UI/MCP data roots, schema/package data and the `kb.ingest.ingest_horizon_payload` admission boundary with and without the information package installed.
- [x] Payload-carried `radar_ref` (resolved 2026-10-04, static + suite evidence). `kb.ingest.ingest_horizon_payload` now reads `radar_ref` from the payload and refuses a payload without it, and the producer injects the validated pin, so a run can no longer be recorded against a guessed revision. Evidence: `tests/test_ingest.py::TestRadarRefProvenance`; producer side in `information_assistant/production.py::collect_and_ingest`.
- [ ] Verify in an isolated workspace with explicit versions and data paths. Record commands, environment, results and unresolved failures.

## P3 — Behavioral evidence

- [ ] Run admission/store/ingest/MCP/UI tests against temporary stores; check duplicate IDs, revision provenance, append-only accounting, backup/restore and knowledge wiki links. Database migrations are not part of P1.
- [x] Source-governance UI failures resolved (2026-10-04, static + suite evidence). They were never a UI defect: `agent-tools` resolves the Horizon profile set from module-level constants read at import time, defaulting to the process CWD, and the migration moved the canonical profile set to Information Assistant. `tests/conftest.py` now pins both constants to this repository's structural fixtures, the fixture config declares a matching `profiles_dir`, and `TestFixtureWiring` guards the wiring. Evidence: whole suite green without any external environment variable (317 passed, 4 skipped). Remaining interface limitation recorded in [sibling-repo-failures.md](../sibling-repo-failures.md) §4.
- [ ] Preserve baseline results and independent acceptance criteria. Keep deterministic checks, model judgment and human evidence separate.
- Failures observed in sibling repositories are recorded in [sibling-repo-failures.md](../sibling-repo-failures.md); they are not KB defects and are not fixed here.

## P4 — Publication and presentation

- [ ] Correct stale LangGraph descriptions only as part of the website/Profile publication change; link actual evidence.
- Local product/tool/skill directory relocation was brought forward into P1; do not repeat it.
- Commit, remote repository creation, push, pin advancement and deployment require an explicit request.

## P5 — Remaining integrations

- [ ] Keep finance/CRM/learning integrations behind public APIs and explicit ownership.

## Entry conditions and completion

Start from the local migration report and current repository instructions. Inspect unresolved static findings before running tests. Use existing dependencies and isolated environments. Never operate on actual user data while executing fixture validation.

Complete a checkbox only with retained evidence, including exact revision/host/model where applicable. Keep experiments that did not run marked pending. The P1 request explicitly did not ask for runtime verification.
