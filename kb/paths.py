"""Explicit instance data location, separate from installed product code."""
import os
from pathlib import Path


def data_root() -> Path:
    return Path(os.environ.get("KB_DATA_ROOT", str(Path.home() / ".local/share/agent-knowledge"))).expanduser()
