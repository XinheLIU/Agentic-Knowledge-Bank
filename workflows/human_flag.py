"""HumanFlag node: preserve failed review batches outside the article store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflows.state import KBState

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PENDING_REVIEW_DIR = PROJECT_ROOT / "knowledge" / "pending_review"


def write_pending_review(
    payload: dict[str, Any],
    pending_dir: Path = PENDING_REVIEW_DIR,
) -> Path:
    pending_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = pending_dir / f"pending-{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def human_flag_node(state: KBState) -> dict[str, bool]:
    plan = state.get("plan", {})
    pending_review_dir = Path(state.get("pending_review_dir", PENDING_REVIEW_DIR))
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iterations_used": state.get("iteration", 0),
        "max_iterations": plan.get("max_iterations", 3),
        "last_feedback": state.get("review_feedback", ""),
        "analyses": state.get("analyses", []),
    }

    if not state.get("dry_run", False):
        path = write_pending_review(payload, pending_dir=pending_review_dir)
        print(f"[HumanFlag] 已保存到 {path}")
    else:
        print("[HumanFlag] dry_run=True，跳过 pending_review 写入")

    return {"needs_human_review": True}
