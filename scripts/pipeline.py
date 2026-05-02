"""Compatibility re-export for pipeline/pipeline.py.

The implementation lives in pipeline/pipeline.py. This module keeps the old
scripts/ import path available for references that still point there.

It can also be run directly:
    python3 scripts/pipeline.py --sources github --limit 5
"""

import importlib.util
import sys
from pathlib import Path

# Load the concrete file to avoid ambiguity between the package and this module.
_real_path = Path(__file__).parent.parent / "pipeline" / "pipeline.py"
_spec = importlib.util.spec_from_file_location("pipeline_real", _real_path)
_real = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_real"] = _real
_spec.loader.exec_module(_real)

collect_github = _real.collect_github
collect_rss = _real.collect_rss
step_collect = _real.step_collect
step_analyze = _real.step_analyze
step_organize = _real.step_organize
step_save = _real.step_save
main = _real.main

if __name__ == "__main__":
    main()
