"""KB test harness: pin provider-tooling profile resolution to repo fixtures.

``agent-tools`` resolves the Horizon profile set from module-level constants:
``HORIZON_CONFIG_ROOT`` is read **at import time** and defaults to the process
CWD, and ``PROFILES_DIR`` is derived as ``<root>/horizon-profiles``.

The canonical profile set no longer lives in this repository — it moved to
Information Assistant with the collection owner. Without intervention a bare
``pytest`` run from this repository would therefore resolve
``<cwd>/horizon-profiles`` (absent here) and the source-governance tests would
fail on a missing directory rather than on the behaviour they describe.

So this harness pins both consumers to the **structural fixture set** under
``tests/fixtures/``. The fixture profile set is a shape-only copy: the
canonical ``ai-kb-personal`` content (routing, rubric, enrichment guidance) is
owned by Information Assistant and must not be duplicated here.

Two distinct constants are pinned on purpose:

* :data:`agent_tools.horizon.setup.PROFILES_DIR` is what
  ``validate_config`` compares a config's *declared* ``processing.profiles_dir``
  against, so it is pinned to the path the fixture config declares.
* :data:`agent_tools.horizon.source_config.PROFILES_DIR` is what
  ``load_profiles`` must be able to *read*, so it is pinned to the on-disk
  fixture set.

``tests/test_ui_canonical.py::TestFixtureWiring`` asserts both, so the wiring
cannot rot silently.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Root the fixture Horizon checkout lives under (``config/horizon`` + profiles).
FIXTURE_CONFIG_ROOT = FIXTURES

#: Structural profile set actually read from disk by ``load_profiles``.
FIXTURE_PROFILES_DIR = FIXTURES / "horizon-profiles"

#: The fixture Horizon config the UI source-governance tests drive.
FIXTURE_CONFIG_PATH = FIXTURES / "horizon" / "data" / "config.json"


def declared_profiles_dir() -> str:
    """The ``processing.profiles_dir`` the fixture config declares."""
    payload = json.loads(FIXTURE_CONFIG_PATH.read_text(encoding="utf-8"))
    return str(payload["processing"]["profiles_dir"])


# Must be set before agent_tools is imported anywhere in the suite, because the
# library binds its constants at import time.
os.environ.setdefault("HORIZON_CONFIG_ROOT", str(FIXTURE_CONFIG_ROOT))

import agent_tools.horizon.setup as _horizon_setup  # noqa: E402
import agent_tools.horizon.source_config as _source_config  # noqa: E402

# `validate_config` compares against this value as a declared-path identity
# check; it never touches the filesystem with it.
_horizon_setup.PROFILES_DIR = Path(declared_profiles_dir())

# `set_source_enabled` reads the profile set through this constant.
_source_config.REPO_ROOT = FIXTURE_CONFIG_ROOT
_source_config.PROFILES_DIR = FIXTURE_PROFILES_DIR
