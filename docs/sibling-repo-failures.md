# Sibling-repository test failures

Last updated: 2026-10-04

Failures observed in sibling repositories while verifying the Horizon-run
surface eviction from this repository. They are **recorded, not fixed here**:
each belongs to the owning repository and touches another repo's test
baselines. This file is the handoff so the evidence is not lost.

## Scope and limits

- Only failures **not** caused by this repository's change are listed. Nothing
  in this repository's own suite is failing; the KB baseline at the time of
  writing is 317 passed, 4 skipped, 0 failed.
- **No isolated environment was created.** `information-assistant` and
  `agent-tools` have no `.venv` of their own, so their suites were run with this
  repository's interpreter plus `PYTHONPATH` pointing at the sibling sources.
  That is a smoke check, not the isolated-install acceptance that P2 requires.
  A failure listed as environmental below could still hide a second, real
  failure that only appears under a proper install.
- Reproduction commands are shown with the paths used. Substitute your own
  workspace root.

## 1. information-assistant — doctor requires an installed checkout

| | |
|---|---|
| Test | `tests/test_operator_surface.py::TestDoctor::test_doctor_reports_pin_and_launch` |
| Result | 1 failed, 65 passed |
| Assertion | `assert payload["ok"] is True` → `False` |

**Cause: environment, not code.** `_doctor` reports
`horizon_dir not found: /Users/xhl/.local/share/agent-tools/Horizon`, the pin's
`default_checkout_dir`. The pinned Horizon checkout is not installed in this
workspace, so the precondition the test assumes does not hold.

**Evidence separating cause from code.** Running the same command against an
existing directory returns a clean report, so `_doctor`'s logic is intact:

```console
$ mkdir -p /tmp/hz-diag && touch /tmp/hz-diag/pyproject.toml
$ python -c "from information_assistant import operator as cli; print(cli.main(['--horizon-dir','/tmp/hz-diag','doctor']))"
doctor: {"config_path": "data/config.json", "errors": [], "horizon_dir": "/tmp/hz-diag",
         "launch": "uv run --frozen horizon-mcp", "missing_env": [], "ok": true,
         "pin": "596e2b1", "unknown_sources": [], "warnings": []}
0
```

**Owner action.** Install the pinned checkout (`horizon-setup install`, then
`horizon-setup doctor`) before running this suite, or mark the test as requiring
a provisioned checkout. Do not weaken `ok` to make it pass.

## 2. agent-tools — pin file baseline is stale

| | |
|---|---|
| Test | `tests/test_horizon_packaging.py::TestPinFile::test_committed_pin_matches_ticket_01` |
| Result | 2 failed, 60 passed (with the next entry) |
| Assertion | `assert pin["default_checkout_dir"] == "../reference/Horizon"` |

`horizon-pin.json` now declares
`"default_checkout_dir": "~/.local/share/agent-tools/Horizon"`, because the
migration moved the checkout out of an in-repo `reference/` directory. The
test still encodes the pre-migration value. The pin's other fields (`radar`,
40-hex `revision`, `revision_prefix`, `launch_command`) all match, so only this
one literal is stale.

**Owner action.** Update the expected value, or assert the property that
matters (the checkout is outside any repository working tree) instead of a
fixed path.

## 3. agent-tools — profile date baseline is stale

| | |
|---|---|
| Test | `tests/test_horizon_packaging.py::TestSourceCoverage::test_profile_markdowns_carry_last_updated` |
| Result | as above |
| Assertion | `assert "Last updated: 2026-09-12" in text` → files carry `2026-10-04` |

The profile Markdown files were re-dated by the migration
(`match.md`, `analysis.md`, `enrichment.md`). The test holds `2026-09-12`
literally.

**Owner action.** Assert that a `Last updated` marker is present and
ISO-parseable rather than pinning one date, which is what the workspace
convention actually requires.

## 4. Design limitation: the profile set has no injection point

Not a test failure, but the reason this repository's test harness carries an
explicit shim, and worth fixing in `agent-tools`.

`agent_tools/horizon/source_config.py` binds:

```python
REPO_ROOT = Path(os.environ.get("HORIZON_CONFIG_ROOT", str(Path.cwd()))).expanduser().resolve()
PROFILES_DIR = REPO_ROOT / "horizon-profiles"
```

Both are read **at import time**, and `agent_tools/horizon/setup.py` holds a
second, independent `PROFILES_DIR` used by `validate_config` for its
declared-path check. Consequences:

- A consumer cannot inject a profile directory per call; the only lever is an
  environment variable that must be set before the first import.
- The default is the process CWD, so behaviour depends on where a consumer
  happens to be started from rather than on configuration.
- `set_source_enabled` requires the profile set to be readable even though its
  own inputs do not mention profiles — so a config-editing API can fail for a
  reason that has nothing to do with the edit.

Because the canonical profile set now lives with Information Assistant,
this repository's suite pins both constants to its own structural fixtures in
`tests/conftest.py` (guarded by
`tests/test_ui_canonical.py::TestFixtureWiring`). Pinning library constants
from a consumer's `conftest` is a workaround, not a design.

**Owner action.** Give the seam an explicit parameter — for example
`load_profiles(profiles_dir)` / `set_source_enabled(..., profiles_dir=...)` /
`validate_config(..., profiles_dir=...)` — defaulting to the current constant so
existing callers keep working. That would let this repository's tests pass a
fixture path without patching library internals.

## Reproducing

```bash
# this repository (green baseline)
cd products/Agentic-Knowledge-Bank
PYTHONPATH=".:$WORKSPACE/tools/agent-tools" .venv/bin/python -m pytest tests/ -q

# information-assistant: 1 failure, environmental
cd products/information-assistant
PYTHONPATH=".:$WORKSPACE/tools/agent-tools:$WORKSPACE/products/Agentic-Knowledge-Bank" \
  "$WORKSPACE/products/Agentic-Knowledge-Bank/.venv/bin/python" -m pytest tests/ -q

# agent-tools: 2 failures, stale baselines
cd tools/agent-tools
PYTHONPATH=".:$WORKSPACE/products/Agentic-Knowledge-Bank" \
  "$WORKSPACE/products/Agentic-Knowledge-Bank/.venv/bin/python" -m pytest tests/ -q
```

None of these results discharge P2. Independent installation, host deployment
and live collection still require their own acceptance evidence.
