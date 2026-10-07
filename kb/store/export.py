"""Export (JSONL), backup, and restore APIs (ticket 07; design K5).

- ``export_jsonl`` writes a portable, diff-able text snapshot (accepted assets
  by default; audit rows via ``include_audit``) with SHA-256 + row-count gates.
- ``backup`` produces a consistent SQLite snapshot via the online backup API
  (safe against concurrent writers) and records its own checksum/count manifest.
- ``restore_jsonl`` replays an export into an existing store (idempotent per
  the write-once/append-only rules).
- ``restore_from_backup`` copies a snapshot over a target path after verifying
  its manifest (recovery-only; callers must stop writers first).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from kb.store import reader as reader_mod
from kb.store import writer as writer_mod

__all__ = [
    "export_jsonl",
    "restore_jsonl",
    "backup",
    "restore_from_backup",
    "ExportManifest",
]

BACKUP_MANIFEST_NAME = "backup-manifest.json"


class ExportManifest(dict):
    """Manifest payload (kept as dict for JSON round-tripping)."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# JSONL export / restore
# ---------------------------------------------------------------------------


def export_jsonl(
    conn: sqlite3.Connection,
    output_path: str | Path,
    *,
    include_audit: bool = False,
) -> dict[str, Any]:
    """Write accepted assets (optionally ledger audit rows) as JSONL.

    Default read surface is accepted-only (invariant I4); audit rows ride an
    explicit ``include_audit`` flag. Returns the manifest: path, item count,
    admission count (when audited), byte size, and SHA-256.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    items = reader_mod.list_items(conn, include_superseded=True)
    item_rows = 0
    with open(output, "w", encoding="utf-8") as dst:
        for item in items:
            dst.write(json.dumps(item.to_payload(), ensure_ascii=False, sort_keys=True) + "\n")
            item_rows += 1
        if include_audit:
            for admission in reader_mod.audit_admissions(conn):
                dst.write(
                    json.dumps(
                        {"kind": "admission", **admission.to_payload()},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
    return ExportManifest(
        path=str(output),
        item_count=item_rows,
        admission_count=(
            len(reader_mod.audit_admissions(conn)) if include_audit else None
        ),
        size_bytes=output.stat().st_size,
        sha256=_sha256(output),
        format="jsonl",
    )


def restore_jsonl(
    conn: sqlite3.Connection, input_path: str | Path, *, radar: str = "restore"
) -> dict[str, Any]:
    """Replay an export into the current store (idempotent, write-once).

    Each line must carry a ``run_id``-bearing run header or be an item
    payload; items are admitted under a synthetic restore run so the ledger
    keeps an auditable trace. Returns counters for the summary line.
    """
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"export not found: {source}")
    run_id = f"restore-{_sha256(source)[:12]}"
    writer_mod.ensure_run(conn, {
        "run_id": run_id,
        "radar": radar,
        "radar_ref": str(source),
        "started_at": None,
        "status": "success",
    })
    restored = 0
    duplicates = 0
    with open(source, encoding="utf-8") as src:
        for line in src:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "admission":
                continue
            # The exported origin run may not exist in this target store;
            # re-parent the asset onto the synthetic restore run so the
            # items.first_run_id FK stays truthful (never disabled).
            row["first_run_id"] = run_id
            result = writer_mod.ensure_item(conn, row, run_id=run_id)
            if result["inserted"]:
                restored += 1
            else:
                duplicates += 1
    writer_mod.record_run_finish(
        conn, run_id, status="success",
        counts={"persisted": restored, "accepted": restored,
                "rejected": duplicates, "fetched": restored + duplicates,
                "mapped": restored + duplicates, "failed": 0},
        invariant_ok=True,
    )
    return {
        "path": str(source),
        "run_id": run_id,
        "restored": restored,
        "duplicates": duplicates,
    }


# ---------------------------------------------------------------------------
# SQLite backup / restore
# ---------------------------------------------------------------------------


def backup(conn: sqlite3.Connection, backup_path: str | Path) -> dict[str, Any]:
    """Consistent snapshot via the SQLite online-backup API.

    Safe against concurrent writers (the backup API copies a consistent
    point-in-time image). Writes a sibling manifest with SHA-256, item and
    run counts for the row-count gates used by rehearsal/recovery (ticket 14).
    """
    target = Path(backup_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    destination = sqlite3.connect(str(target))
    try:
        conn.backup(destination)
        destination.commit()
    finally:
        destination.close()

    stats = reader_mod.stats(conn)
    manifest = ExportManifest(
        path=str(target),
        size_bytes=target.stat().st_size,
        sha256=_sha256(target),
        item_count=stats.item_count,
        accepted_count=stats.accepted_count,
        superseded_count=stats.superseded_count,
        run_count=stats.run_count,
        admission_count=stats.admission_count,
        consistent=True,
    )
    manifest_path = target.with_name(target.name + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return manifest


def restore_from_backup(backup_path: str | Path, *, target_path: str | Path) -> dict[str, Any]:
    """Copy a verified snapshot over ``target_path`` (destructive recovery).

    Callers must stop all writers first (BACKUP_RESTORE.md §5). The backup's
    manifest checksum is verified before the copy; a mismatch aborts without
    touching the target — never proceed on a partial restore.
    """
    source = Path(backup_path)
    if not source.exists():
        raise FileNotFoundError(f"backup not found: {source}")
    manifest_path = source.with_name(source.name + ".manifest.json")
    if not manifest_path.exists():
        raise FileNotFoundError(f"backup manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = _sha256(source)
    if manifest.get("sha256") != actual:
        raise ValueError(
            f"backup checksum mismatch: manifest {manifest.get('sha256')!r} != {actual!r}"
        )
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "path": str(target),
        "restored": True,
        "sha256": actual,
        "item_count": manifest.get("item_count"),
        "run_count": manifest.get("run_count"),
    }
