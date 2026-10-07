"""Read path: accepted-only default reads with explicit audit channels.

Per invariant I4 (asset model §3.3): readers and export default to
``state='accepted'``; rejected/failed candidates are visible only through the
explicit audit paths over the ledger (``get_admissions`` / ``audit_admissions``).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from kb.store.model import AdmissionRecord, ItemRecord, RunRecord, StoreStats

__all__ = [
    "get_item",
    "list_items",
    "get_run",
    "list_runs",
    "get_admissions",
    "audit_admissions",
    "stats",
    "latest_published_day",
    "story_edges",
]

_ITEM_SELECT = """
SELECT id, state, superseded_by, source_type, title, url, author, published_at,
       fetched_at, story_fp, profile, profile_method, profile_confidence,
       profile_reason, score, score_reason, summary, content_main,
       content_comments, metadata_json, first_seen_at, first_run_id, updated_at
FROM items
"""


def _row_to_item(row: sqlite3.Row, tags: tuple[str, ...] = ()) -> ItemRecord:
    return ItemRecord(
        id=str(row["id"]),
        state=str(row["state"]),
        superseded_by=row["superseded_by"],
        source_type=str(row["source_type"]),
        title=str(row["title"]),
        url=str(row["url"]),
        author=row["author"],
        published_at=row["published_at"],
        fetched_at=str(row["fetched_at"]),
        story_fp=row["story_fp"],
        profile=row["profile"],
        profile_method=row["profile_method"],
        profile_confidence=row["profile_confidence"],
        profile_reason=row["profile_reason"],
        score=row["score"],
        score_reason=row["score_reason"],
        summary=row["summary"],
        content_main=row["content_main"],
        content_comments=row["content_comments"],
        metadata_json=row["metadata_json"],
        first_seen_at=str(row["first_seen_at"]),
        first_run_id=str(row["first_run_id"]),
        updated_at=str(row["updated_at"]),
        tags=tags,
    )


def _tags_for(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {item_id: () for item_id in item_ids}
    if not item_ids:
        return tags
    placeholders = ", ".join("?" for _ in item_ids)
    for item_id, tag in conn.execute(
        f"SELECT item_id, tag FROM tags WHERE item_id IN ({placeholders}) ORDER BY tag",
        item_ids,
    ):
        tags[str(item_id)] += (str(tag),)
    return tags


def get_item(
    conn: sqlite3.Connection, item_id: str, *, include_superseded: bool = False
) -> ItemRecord | None:
    """Fetch one asset; superseded rows need the explicit opt-in flag (I4)."""
    sql = _ITEM_SELECT + " WHERE id = ?"
    if not include_superseded:
        sql += " AND state = 'accepted'"
    row = conn.execute(sql, (item_id,)).fetchone()
    if row is None:
        return None
    tags = _tags_for(conn, [str(row["id"])])
    return _row_to_item(row, tags[str(row["id"])])


def list_items(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    source_type: str | None = None,
    include_superseded: bool = False,
    limit: int | None = None,
) -> list[ItemRecord]:
    """List assets, accepted-only by default; ordered by published desc."""
    clauses: list[str] = []
    params: list[Any] = []
    if not include_superseded:
        clauses.append("state = 'accepted'")
    if source_type is not None:
        clauses.append("source_type = ?")
        params.append(source_type)
    if q:
        lowered = q.lower()
        clauses.append("(lower(title) LIKE ? OR lower(summary) LIKE ?)")
        params.extend((f"%{lowered}%", f"%{lowered}%"))
    sql = _ITEM_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY published_at DESC, id ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    ids = [str(row["id"]) for row in rows]
    tags = _tags_for(conn, ids)
    return [_row_to_item(row, tags[str(row["id"])]) for row in rows]


def get_run(conn: sqlite3.Connection, run_id: str) -> RunRecord | None:
    """One run row (audit path: runs are always readable)."""
    row = conn.execute(
        """
        SELECT run_id, radar, radar_ref, config_hash, started_at, finished_at,
               status, fetched, mapped, accepted, rejected, failed, persisted,
               invariant_ok, sources_json
        FROM runs WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return RunRecord(
        run_id=str(row["run_id"]),
        radar=str(row["radar"]),
        radar_ref=str(row["radar_ref"]),
        config_hash=row["config_hash"],
        started_at=str(row["started_at"]),
        finished_at=row["finished_at"],
        status=str(row["status"]),
        fetched=int(row["fetched"]),
        mapped=int(row["mapped"]),
        accepted=int(row["accepted"]),
        rejected=int(row["rejected"]),
        failed=int(row["failed"]),
        persisted=int(row["persisted"]),
        invariant_ok=bool(row["invariant_ok"]),
        sources_json=row["sources_json"],
    )


def list_runs(conn: sqlite3.Connection, *, limit: int | None = None) -> list[RunRecord]:
    """List runs, newest first."""
    sql = (
        "SELECT run_id, radar, radar_ref, config_hash, started_at, finished_at, "
        "status, fetched, mapped, accepted, rejected, failed, persisted, "
        "invariant_ok, sources_json FROM runs ORDER BY started_at DESC, run_id ASC"
    )
    params: list[Any] = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    return [
        RunRecord(
            run_id=str(row["run_id"]),
            radar=str(row["radar"]),
            radar_ref=str(row["radar_ref"]),
            config_hash=row["config_hash"],
            started_at=str(row["started_at"]),
            finished_at=row["finished_at"],
            status=str(row["status"]),
            fetched=int(row["fetched"]),
            mapped=int(row["mapped"]),
            accepted=int(row["accepted"]),
            rejected=int(row["rejected"]),
            failed=int(row["failed"]),
            persisted=int(row["persisted"]),
            invariant_ok=bool(row["invariant_ok"]),
            sources_json=row["sources_json"],
        )
        for row in conn.execute(sql, params)
    ]


_ADMISSION_SELECT = """
SELECT run_id, item_id, outcome, policy_id, policy_version, reason_codes,
       evidence_json, duplicate_of, decided_at
FROM admissions
"""


def _row_to_admission(row: sqlite3.Row) -> AdmissionRecord:
    try:
        codes = tuple(str(code) for code in json.loads(row["reason_codes"]))
    except (TypeError, ValueError):
        codes = ()
    return AdmissionRecord(
        run_id=str(row["run_id"]),
        item_id=str(row["item_id"]),
        outcome=str(row["outcome"]),
        policy_id=str(row["policy_id"]),
        policy_version=str(row["policy_version"]),
        reason_codes=codes,
        evidence_json=row["evidence_json"],
        duplicate_of=row["duplicate_of"],
        decided_at=str(row["decided_at"]),
    )


def get_admissions(
    conn: sqlite3.Connection, item_id: str, *, run_id: str | None = None
) -> list[AdmissionRecord]:
    """Explicit audit path: every ledger decision for one item id."""
    sql = _ADMISSION_SELECT + " WHERE item_id = ?"
    params: list[Any] = [item_id]
    if run_id is not None:
        sql += " AND run_id = ?"
        params.append(run_id)
    sql += " ORDER BY decided_at ASC, run_id ASC"
    return [_row_to_admission(row) for row in conn.execute(sql, params)]


def audit_admissions(
    conn: sqlite3.Connection,
    *,
    run_id: str | None = None,
    outcome: str | None = None,
    limit: int | None = None,
) -> list[AdmissionRecord]:
    """Explicit audit path: ledger rows filtered by run/outcome (I4)."""
    clauses: list[str] = []
    params: list[Any] = []
    if run_id is not None:
        clauses.append("run_id = ?")
        params.append(run_id)
    if outcome is not None:
        clauses.append("outcome = ?")
        params.append(outcome)
    sql = _ADMISSION_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY decided_at ASC, run_id ASC, item_id ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    return [_row_to_admission(row) for row in conn.execute(sql, params)]


def stats(conn: sqlite3.Connection) -> StoreStats:
    """Whole-store counters (accepted-asset-only item count by default)."""
    item_count = int(conn.execute("SELECT COUNT(*) FROM items WHERE state='accepted'").fetchone()[0])
    superseded = int(conn.execute("SELECT COUNT(*) FROM items WHERE state='superseded'").fetchone()[0])
    run_count = int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
    admission_count = int(conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0])
    tag_count = int(conn.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0])
    return StoreStats(
        item_count=item_count,
        accepted_count=item_count,
        superseded_count=superseded,
        run_count=run_count,
        admission_count=admission_count,
        tag_count=tag_count,
    )


def latest_published_day(conn: sqlite3.Connection) -> str | None:
    """Newest accepted-asset publish day (digest default), or None when empty."""
    row = conn.execute(
        "SELECT MAX(substr(published_at, 1, 10)) FROM items WHERE state = 'accepted' "
        "AND published_at IS NOT NULL"
    ).fetchone()
    value = row[0] if row else None
    return str(value) if value else None


def story_edges(conn: sqlite3.Connection, item_id: str) -> list[dict[str, Any]]:
    """Reserved graph links for one asset (``edges``; same-story joins)."""
    edges: list[dict[str, Any]] = []
    for src, dst, kind, weight, created in conn.execute(
        """
        SELECT src_id, dst_id, kind, weight, created_at FROM edges
        WHERE src_id = ? OR dst_id = ?
        ORDER BY created_at ASC, src_id ASC, dst_id ASC
        """,
        (item_id, item_id),
    ):
        edges.append({
            "src_id": str(src),
            "dst_id": str(dst),
            "kind": str(kind),
            "weight": weight,
            "created_at": created,
        })
    return edges
