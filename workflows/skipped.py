"""Skipped items audit log.

Append-only line-JSON for articles dropped by analyzer, reviewer, or organizer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKIPPED_PATH = PROJECT_ROOT / "knowledge" / "articles" / "_skipped.jsonl"


def append_skipped(
    item_id: str,
    source: str,
    source_url: str,
    stage: str,
    reason: str,
    skipped_path: Path = SKIPPED_PATH,
) -> None:
    """Atomically append a skipped record to _skipped.jsonl.

    Args:
        item_id: Article id (same namespace as articles).
        source: Human-readable source name.
        source_url: Original URL.
        stage: Node that dropped the item (analyzer|reviewer|organizer).
        reason: Short explanation.
        skipped_path: Override path for tests.
    """
    record: dict[str, Any] = {
        "id": item_id,
        "source": source,
        "source_url": source_url,
        "stage": stage,
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"

    skipped_path.parent.mkdir(parents=True, exist_ok=True)
    with open(skipped_path, "a", encoding="utf-8") as f:
        f.write(line)
        os.fsync(f.fileno())


def read_skipped_ids(skipped_path: Path = SKIPPED_PATH) -> set[str]:
    """Return all ids ever recorded in _skipped.jsonl."""
    ids: set[str] = set()
    if not skipped_path.exists():
        return ids

    with open(skipped_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_id = record.get("id")
            if isinstance(item_id, str):
                ids.add(item_id)
    return ids
