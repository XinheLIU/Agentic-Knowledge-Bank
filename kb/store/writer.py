"""Write path: write-once items, append-only ledger, runs, story edges.

Enforces the canonical model (ticket 02) at the persistence layer:

- **Write-once assets** — an accepted asset is never updated in content; a
  re-presented same-ID item is a ``DUPLICATE_ID`` no-op (asset model §1.1/§2).
- **Partial URL uniqueness** — a partial unique index on
  ``items(url) WHERE state='accepted'``; a same-URL candidate becomes
  ``DUPLICATE_URL`` (pointing at the winner) without an items row (§1.3).
- **Append-only admissions** — insert-only ledger keyed ``(run_id, item_id)``
  with ordered ``reason_codes`` from ``kb/model.py``; the writer rejects
  unregistered codes and validates the ``duplicate_of`` pointer.
- **Supersede is one transaction** — old asset flips to ``superseded`` and the
  accepted successor inserts atomically; the deferred FK allows the cycle.
- **Run invariants I1–I5** gate persistence; a violated invariant rolls the
  run back and persists nothing (asset model §3.3).
"""

from __future__ import annotations

import contextlib
import itertools
import json
import sqlite3
import time
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from kb import model as kb_model

if TYPE_CHECKING:  # pragma: no cover - typing only
    from kb.store.model import RunRecord

__all__ = [
    "StoreWriteError",
    "InvariantViolation",
    "WriteConflict",
    "normalize_item_payload",
    "ensure_run",
    "record_run_finish",
    "ensure_item",
    "record_rejections",
    "supersede_item",
    "add_story_edge",
    "ingest_run",
]

POLICY_ID_DEFAULT = "admission-policy"
POLICY_VERSION_DEFAULT = "0.1.0"


class StoreWriteError(RuntimeError):
    """A write violated the canonical store contract."""


class InvariantViolation(StoreWriteError):
    """A run invariant (I1–I5) failed; nothing was persisted for the run."""


class WriteConflict(StoreWriteError):
    """A precondition conflict (unknown run, unknown pointer, bad state)."""


# ---------------------------------------------------------------------------
# payload normalization
# ---------------------------------------------------------------------------

_ITEM_TEXT_FIELDS = (
    "title", "url", "fetched_at", "first_seen_at", "first_run_id", "updated_at",
)
_ITEM_OPTIONAL_TEXT = (
    "author", "published_at", "story_fp", "profile", "profile_method",
    "profile_reason", "score_reason", "summary", "content_main",
    "content_comments", "metadata_json",
)


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


_SP_COUNTER = itertools.count()


@contextlib.contextmanager
def _write_txn(conn: sqlite3.Connection):
    """Write transaction safe under both autocommit and caller-owned transactions.

    When no transaction is open this issues ``BEGIN IMMEDIATE``/``COMMIT``
    (rollback on error). When the caller already holds a transaction (e.g. a
    batch ingest or a migration driver), it nests via ``SAVEPOINT`` so the
    outer commit discipline stays with the caller.
    """
    if conn.in_transaction:
        savepoint = f"kb_sp_{id(conn):x}_{next(_SP_COUNTER)}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            yield
        except BaseException:
            conn.execute(f"ROLLBACK TO {savepoint}")
            conn.execute(f"RELEASE {savepoint}")
            raise
        else:
            conn.execute(f"RELEASE {savepoint}")
    else:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")


def normalize_item_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an item payload to canonical ``items`` columns.

    Derives ``story_fp`` via the ``kb/model.py`` single-owner algorithm when
    absent, and JSON-encodes dict/list ``metadata_json`` inputs.
    """
    payload = dict(item)
    item_id = payload.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise StoreWriteError("item id is required (minted by the radar mapper)")
    for field_name in ("title", "url", "fetched_at"):
        if not isinstance(payload.get(field_name), str) or not payload[field_name].strip():
            raise StoreWriteError(f"item {item_id}: {field_name} is required")
    if payload.get("state") is None:
        payload["state"] = "accepted"
    if payload["state"] not in kb_model.ASSET_STATES:
        raise StoreWriteError(
            f"item {item_id}: state {payload['state']!r} not in {kb_model.ASSET_STATES}"
        )
    for field_name in _ITEM_TEXT_FIELDS:
        value = payload.get(field_name)
        payload[field_name] = str(value) if value is not None else value
    # Encode structured metadata BEFORE the optional-text str() coercion,
    # otherwise a dict/list metadata_json would be stringified as a Python
    # repr instead of JSON.
    metadata = payload.get("metadata_json")
    if isinstance(metadata, (dict, list)):
        payload["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    for field_name in _ITEM_OPTIONAL_TEXT:
        if field_name in payload and payload[field_name] is not None:
            payload[field_name] = str(payload[field_name])
    if not isinstance(payload.get("first_seen_at"), str) or not payload["first_seen_at"].strip():
        payload["first_seen_at"] = _utcnow()
    if not isinstance(payload.get("updated_at"), str) or not payload["updated_at"].strip():
        payload["updated_at"] = _utcnow()
    if not isinstance(payload.get("first_run_id"), str) or not payload["first_run_id"].strip():
        # Inherit the run context when the mapper doesn't stamp it (the run
        # is known at admission time in the canonical flow).
        payload["first_run_id"] = "pending"
        payload["_first_run_inherited"] = True
    if payload.get("story_fp") is None:
        payload["story_fp"] = kb_model.story_fingerprint(payload["title"], payload["url"])
    tags = payload.get("tags") or ()
    if not isinstance(tags, (list, tuple, set)):
        raise StoreWriteError(f"item {item_id}: tags must be a list")
    payload["tags"] = sorted({str(tag) for tag in tags if str(tag).strip()})
    return payload


def _persist_derived_fields(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    """Project mapper-only derived fields into the limited consumer surface.

    The canonical ``items`` row stays write-once (asset model §5): only the
    known ``items`` columns are inserted. Two mapper outputs need a
    consumer-visible home anyway, so the writer projects them into the
    bounded metadata document — a one-line, transparent split. Nothing else
    (no raw upstream blobs, no audit data) may ride along here.

    - ``horizon_extra`` — the bounded unknown-upstream-fields projection
      (ticket 08); rendered under ``metadata_json["horizon_extra"]``.
    - ``artifacts`` — localized enrichment blocks (ticket 08); rendered as a
      bounded summary under ``metadata_json["artifacts"]``.

    A no-op when the mapper supplied neither key (payload untouched, so a
    caller-supplied metadata document survives verbatim).
    """
    metadata = payload.get("metadata_json")
    doc: dict[str, Any]
    if isinstance(metadata, str):
        try:
            doc = json.loads(metadata)
        except ValueError:
            doc = {"value": metadata}
        if not isinstance(doc, dict):
            doc = {"value": doc}
    elif isinstance(metadata, dict):
        doc = dict(metadata)
    else:
        doc = {}
    touched = False
    artifacts = payload.pop("artifacts", None)
    if artifacts:
        doc["artifacts"] = [
            {
                "language": a.get("language"),
                "title": a.get("title"),
                "blocks": [
                    {
                        "title": b.get("title"),
                        "content": b.get("content"),
                        "is_primary": bool(b.get("is_primary")),
                    }
                    for b in a.get("blocks") or []
                ],
            }
            for a in artifacts
        ]
        touched = True
    extras = payload.pop("horizon_extra", None)
    if extras is not None:
        doc["horizon_extra"] = extras
        touched = True
    if touched:
        payload["metadata_json"] = json.dumps(doc, ensure_ascii=False, sort_keys=True)


def _validate_reason_codes(reason_codes: Sequence[str]) -> list[str]:
    if not reason_codes:
        raise StoreWriteError("reason_codes must be a non-empty ordered array")
    codes = list(reason_codes)
    for code in codes:
        if not kb_model.ReasonCode.is_registered(code):
            raise StoreWriteError(
                f"reason code {code!r} not in the kb/model.py registry (O2: no second vocabulary)"
            )
    return codes


def _validate_admission_row(row: Mapping[str, Any]) -> dict[str, Any]:
    outcome = row.get("outcome")
    if outcome not in kb_model.OUTCOMES:
        raise StoreWriteError(f"outcome {outcome!r} not in {kb_model.OUTCOMES}")
    codes = _validate_reason_codes(row.get("reason_codes") or [])
    normalized = dict(row)
    normalized["reason_codes"] = json.dumps(codes, ensure_ascii=False)
    if outcome == "accepted" and any(code.startswith("NEG_") for code in codes):
        raise StoreWriteError("accepted row cannot carry NEG_* reason codes")
    return normalized


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------


def ensure_run(conn: sqlite3.Connection, run: RunRecord | Mapping[str, Any]) -> None:
    """Insert the run row if absent (idempotent); existing runs are untouched."""
    payload = run.to_payload() if hasattr(run, "to_payload") else dict(run)
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise StoreWriteError("run_id is required")
    status = payload.get("status")
    if status not in kb_model.RUN_STATUSES:
        raise StoreWriteError(f"run status {status!r} not in {kb_model.RUN_STATUSES}")
    conn.execute(
        """
        INSERT INTO runs (run_id, radar, radar_ref, config_hash, started_at,
                          finished_at, status, fetched, mapped, accepted,
                          rejected, failed, persisted, invariant_ok, sources_json)
        VALUES (:run_id, :radar, :radar_ref, :config_hash, :started_at,
                :finished_at, :status, :fetched, :mapped, :accepted,
                :rejected, :failed, :persisted, :invariant_ok, :sources_json)
        ON CONFLICT(run_id) DO NOTHING
        """,
        {
            "run_id": run_id,
            "radar": payload.get("radar") or "horizon",
            "radar_ref": payload.get("radar_ref") or "unpinned",
            "config_hash": payload.get("config_hash"),
            "started_at": payload.get("started_at") or _utcnow(),
            "finished_at": payload.get("finished_at"),
            "status": status,
            "fetched": int(payload.get("fetched") or 0),
            "mapped": int(payload.get("mapped") or 0),
            "accepted": int(payload.get("accepted") or 0),
            "rejected": int(payload.get("rejected") or 0),
            "failed": int(payload.get("failed") or 0),
            "persisted": int(payload.get("persisted") or 0),
            "invariant_ok": 1 if payload.get("invariant_ok", True) else 0,
            "sources_json": (
                json.dumps(payload["sources_json"], ensure_ascii=False)
                if isinstance(payload.get("sources_json"), (dict, list))
                else payload.get("sources_json")
            ),
        },
    )


def record_run_finish(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    counts: Mapping[str, int],
    invariant_ok: bool,
    config_hash: str | None = None,
    sources_json: str | None = None,
) -> None:
    """Finalize a run's durable accounting (called after ledger + items commit)."""
    updated = conn.execute(
        """
        UPDATE runs SET finished_at = :finished_at, status = :status,
                        fetched = :fetched, mapped = :mapped, accepted = :accepted,
                        rejected = :rejected, failed = :failed, persisted = :persisted,
                        invariant_ok = :invariant_ok,
                        config_hash = COALESCE(:config_hash, config_hash),
                        sources_json = COALESCE(:sources_json, sources_json)
        WHERE run_id = :run_id
        """,
        {
            "run_id": run_id,
            "finished_at": _utcnow(),
            "status": status,
            "fetched": int(counts.get("fetched", 0)),
            "mapped": int(counts.get("mapped", 0)),
            "accepted": int(counts.get("accepted", 0)),
            "rejected": int(counts.get("rejected", 0)),
            "failed": int(counts.get("failed", 0)),
            "persisted": int(counts.get("persisted", 0)),
            "invariant_ok": 1 if invariant_ok else 0,
            "config_hash": config_hash,
            "sources_json": sources_json,
        },
    )
    if updated.rowcount != 1:
        raise WriteConflict(f"run {run_id!r} not found for finish")


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------

_ITEM_COLUMNS = (
    "id", "state", "superseded_by", "source_type", "title", "url", "author",
    "published_at", "fetched_at", "story_fp", "profile", "profile_method",
    "profile_confidence", "profile_reason", "score", "score_reason", "summary",
    "content_main", "content_comments", "metadata_json", "first_seen_at",
    "first_run_id", "updated_at",
)

def _insert_item(conn: sqlite3.Connection, payload: Mapping[str, Any]) -> None:
    payload = dict(payload)
    inherited_run = payload.pop("_first_run_inherited", False)
    if inherited_run:
        # stamped by the caller below via ensure_item/ingest_run context
        pass
    columns = [c for c in _ITEM_COLUMNS if c in payload]
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.execute(
        f"INSERT INTO items ({', '.join(columns)}) VALUES ({placeholders})",
        {c: payload[c] for c in columns},
    )
    for tag in payload.get("tags", ()):
        conn.execute(
            "INSERT OR IGNORE INTO tags (item_id, tag) VALUES (?, ?)",
            (payload["id"], tag),
        )


def ensure_item(
    conn: sqlite3.Connection,
    item: Mapping[str, Any],
    *,
    run_id: str,
    policy_id: str = POLICY_ID_DEFAULT,
    policy_version: str = POLICY_VERSION_DEFAULT,
    evidence_json: str | None = None,
) -> dict[str, int]:
    """Admit one accepted item under the canonical identity rules.

    Precedence per asset model §1.2: a same-ID accepted asset (or any
    same-ID item row) makes this occurrence a ``DUPLICATE_ID`` no-op — the
    stored row is never updated (write-once). A different item whose URL
    collides with an accepted asset becomes a ``DUPLICATE_URL`` ledger row
    (no items row; the partial unique index stays intact). Returns
    ``{"outcome": ..., "duplicate_of": ...}``-shaped counters:
    ``{"inserted": 0/1, "duplicate_id": 0/1, "duplicate_url": 0/1}``.
    """
    payload = normalize_item_payload(item)
    payload.pop("_first_run_inherited", None)
    if not isinstance(payload.get("first_run_id"), str) or payload["first_run_id"] == "pending":
        payload["first_run_id"] = run_id
    item_id = payload["id"]
    now = _utcnow()

    with _write_txn(conn):
        already_decided = conn.execute(
            "SELECT outcome, duplicate_of FROM admissions WHERE run_id = ? AND item_id = ?",
            (run_id, item_id),
        ).fetchone()
        if already_decided is not None:
            # Precedence 0: same (run_id, item_id) already decided in this run
            # is a pure no-op — the ledger is append-only, nothing appended.
            return {
                "inserted": 0,
                "duplicate_id": 1 if already_decided["outcome"] == "rejected" else 0,
                "duplicate_url": 0,
                "replayed": True,
            }
        existing = conn.execute(
            "SELECT id, url FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if existing is not None:
            # Write-once: never update an accepted asset; record the dup decision.
            _append_admission(conn, run_id=run_id, item_id=item_id, outcome="rejected",
                              policy_id=policy_id, policy_version=policy_version,
                              reason_codes=["DUPLICATE_ID"], evidence_json=None,
                              duplicate_of=str(existing["id"]), decided_at=now)
            return {"inserted": 0, "duplicate_id": 1, "duplicate_url": 0}

        url_winner = conn.execute(
            "SELECT id FROM items WHERE url = ? AND state = 'accepted'", (payload["url"],)
        ).fetchone()
        if url_winner is not None:
            _append_admission(conn, run_id=run_id, item_id=item_id, outcome="rejected",
                              policy_id=policy_id, policy_version=policy_version,
                              reason_codes=["DUPLICATE_URL"], evidence_json=None,
                              duplicate_of=str(url_winner["id"]), decided_at=now)
            return {"inserted": 0, "duplicate_id": 0, "duplicate_url": 1}

        try:
            _persist_derived_fields(conn, payload)
            _insert_item(conn, payload)
            _append_admission(conn, run_id=run_id, item_id=item_id, outcome="accepted",
                              policy_id=policy_id, policy_version=policy_version,
                              reason_codes=["ACCEPTED"], evidence_json=evidence_json,
                              duplicate_of=None, decided_at=now)
        except sqlite3.IntegrityError as exc:
            raise WriteConflict(f"item {item_id} write conflict: {exc}") from exc
        return {"inserted": 1, "duplicate_id": 0, "duplicate_url": 0}


def _append_admission(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    item_id: str,
    outcome: str,
    policy_id: str,
    policy_version: str,
    reason_codes: Sequence[str],
    evidence_json: str | None,
    duplicate_of: str | None,
    decided_at: str,
) -> None:
    row = _validate_admission_row({
        "run_id": run_id, "item_id": item_id, "outcome": outcome,
        "policy_id": policy_id, "policy_version": policy_version,
        "reason_codes": reason_codes, "evidence_json": evidence_json,
        "duplicate_of": duplicate_of, "decided_at": decided_at,
    })
    if duplicate_of is not None:
        known = conn.execute(
            "SELECT 1 FROM items WHERE id = ? "
            "UNION SELECT 1 FROM admissions WHERE item_id = ? AND run_id != ?",
            (duplicate_of, duplicate_of, run_id),
        ).fetchone()
        if known is None and duplicate_of != item_id:
            raise WriteConflict(
                f"duplicate_of {duplicate_of!r} references no known candidate/asset"
            )
    try:
        conn.execute(
            """
            INSERT INTO admissions (run_id, item_id, outcome, policy_id,
                                    policy_version, reason_codes, evidence_json,
                                    duplicate_of, decided_at)
            VALUES (:run_id, :item_id, :outcome, :policy_id, :policy_version,
                    :reason_codes, :evidence_json, :duplicate_of, :decided_at)
            """,
            row,
        )
    except sqlite3.IntegrityError as exc:
        raise WriteConflict(
            f"append-only ledger violation for ({run_id}, {item_id}): {exc}"
        ) from exc


def record_rejections(
    conn: sqlite3.Connection,
    rows: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    policy_id: str = POLICY_ID_DEFAULT,
    policy_version: str = POLICY_VERSION_DEFAULT,
) -> int:
    """Append rejected/failed ledger rows only (no items rows are created)."""
    appended = 0
    now = _utcnow()
    with _write_txn(conn):
        for row in rows:
            _append_admission(
                conn,
                run_id=run_id,
                item_id=str(row["item_id"]),
                outcome=str(row["outcome"]),
                policy_id=str(row.get("policy_id") or policy_id),
                policy_version=str(row.get("policy_version") or policy_version),
                reason_codes=list(row.get("reason_codes") or []),
                evidence_json=row.get("evidence_json"),
                duplicate_of=row.get("duplicate_of"),
                decided_at=str(row.get("decided_at") or now),
            )
            appended += 1
    return appended


def supersede_item(
    conn: sqlite3.Connection,
    item_id: str,
    *,
    successor_id: str,
    run_id: str,
    policy_id: str = POLICY_ID_DEFAULT,
    policy_version: str = POLICY_VERSION_DEFAULT,
) -> bool:
    """Flip an accepted asset to ``superseded`` behind its accepted successor.

    Both assets must already exist as accepted rows (the successor was
    ingested/accepted first); this API links them. One transaction (asset
    model §1.3): the ledger gains the matching ``supersede`` row keyed by the
    predecessor's item id ("an asset is superseded iff a supersede row
    references it"), and the predecessor's ``superseded_by`` resolves at
    COMMIT under the deferred FK. ``run_id`` must be an ensured run — the
    writer never creates placeholder runs. Returns True when the supersede
    happened, False when the predecessor is already superseded by the same
    successor (idempotent replay).
    """
    now = _utcnow()
    with _write_txn(conn):
        successor = conn.execute(
            "SELECT state FROM items WHERE id = ?", (successor_id,)
        ).fetchone()
        if successor is None:
            raise WriteConflict(
                f"supersede successor {successor_id!r} has no items row; "
                "ingest/accept it first"
            )
        if str(successor["state"]) != "accepted":
            raise WriteConflict(
                f"supersede successor {successor_id!r} is {successor['state']!r}, not accepted"
            )
        predecessor = conn.execute(
            "SELECT state, superseded_by FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if predecessor is None:
            raise WriteConflict(f"supersede target {item_id!r} has no items row")
        if str(predecessor["state"]) == "superseded":
            if str(predecessor["superseded_by"] or "") == successor_id:
                return False  # idempotent replay
            raise WriteConflict(
                f"supersede target {item_id!r} is already superseded by "
                f"{predecessor['superseded_by']!r}"
            )
        if str(predecessor["state"]) != "accepted":
            raise WriteConflict(
                f"supersede target {item_id!r} is {predecessor['state']!r}, not accepted"
            )
        _append_admission(conn, run_id=run_id, item_id=item_id, outcome="supersede",
                          policy_id=policy_id, policy_version=policy_version,
                          reason_codes=["ACCEPTED"], evidence_json=None,
                          duplicate_of=successor_id, decided_at=now)
        conn.execute(
            "UPDATE items SET state = 'superseded', superseded_by = ?, updated_at = ? "
            "WHERE id = ?",
            (successor_id, now, item_id),
        )
        return True


def add_story_edge(
    conn: sqlite3.Connection,
    src_id: str,
    dst_id: str,
    *,
    kind: str = "same_story",
    weight: float | None = None,
) -> bool:
    """Link two same-story assets (dedup precedence 3: linked, never collapsed)."""
    conn.execute(
        """
        INSERT INTO edges (src_id, dst_id, kind, weight, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(src_id, dst_id, kind) DO NOTHING
        """,
        (src_id, dst_id, kind, weight, _utcnow()),
    )
    return True


# ---------------------------------------------------------------------------
# run invariants (asset model §3.3) and batch ingest
# ---------------------------------------------------------------------------


def _check_run_invariants(conn: sqlite3.Connection, run_id: str) -> None:
    """I2/I3 before commit: ledger completeness and count closure."""
    ledger = conn.execute(
        """
        SELECT outcome, COUNT(*) FROM admissions WHERE run_id = ?
        GROUP BY outcome
        """,
        (run_id,),
    ).fetchall()
    by_outcome = {str(outcome): int(count) for outcome, count in ledger}
    accepted = by_outcome.get("accepted", 0)
    supersede = by_outcome.get("supersede", 0)

    items_from_run = conn.execute(
        "SELECT COUNT(*) FROM items WHERE first_run_id = ?", (run_id,)
    ).fetchone()[0]
    if items_from_run != accepted:
        raise InvariantViolation(
            f"I3: run {run_id} has {accepted} accepted ledger rows but "
            f"{items_from_run} items rows"
        )
    for code_row in conn.execute(
        "SELECT outcome, reason_codes, policy_version FROM admissions WHERE run_id = ?",
        (run_id,),
    ):
        if str(code_row[0]) != "accepted" and (not code_row[2] or not code_row[1]):
            raise InvariantViolation(
                f"I3: run {run_id} has a non-accept row missing policy/reasons"
            )
    if supersede:
        for (superseded_id,) in conn.execute(
            "SELECT state FROM items WHERE state = 'superseded' AND superseded_by IS NOT NULL"
        ):
            if superseded_id is None:  # pragma: no cover - defensive
                raise InvariantViolation(f"I3: supersede without successor in run {run_id}")


def ingest_run(
    conn: sqlite3.Connection,
    run: Mapping[str, Any] | Any,
    items: Sequence[Mapping[str, Any] | Any],
    rejections: Sequence[Mapping[str, Any] | Any],
) -> dict[str, Any]:
    """Persist one run atomically: ledger rows, accepted items, run accounting.

    Transactional per asset model §3.3: run invariants I2/I3 are checked
    before COMMIT; any violation rolls back everything so a failed run
    persists nothing. Returns per-outcome counts for the ingest summary.
    """
    payload = run.to_payload() if hasattr(run, "to_payload") else dict(run)
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise StoreWriteError("ingest_run requires run_id")

    with _write_txn(conn):
        # Precedence 0 (asset model §1.2): replaying the same run_id with the
        # same finished accounting mutates nothing — a completed run replays
        # as a pure no-op (I5 idempotent replay).
        existing_run = conn.execute(
            "SELECT status, finished_at FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if (
            existing_run is not None
            and existing_run["finished_at"] is not None
            and not items
            and not rejections
        ):
            return {
                "run_id": run_id,
                "ledger": {},
                "inserted": 0,
                "duplicates": 0,
                "superseded": 0,
                "invariant_ok": True,
                "replayed": True,
            }

        ensure_run(conn, payload)  # idempotent; existing run rows untouched

        counts = {
            "fetched": int(payload.get("fetched") or (len(items) + len(rejections))),
            "mapped": int(payload.get("mapped") or (len(items) + len(rejections))),
            "accepted": 0,
            "rejected": 0,
            "failed": 0,
            "persisted": 0,
        }
        now = _utcnow()
        for row in rejections:
            normalized = row.to_payload() if hasattr(row, "to_payload") else dict(row)
            _append_admission(
                conn,
                run_id=run_id,
                item_id=str(normalized["item_id"]),
                outcome=str(normalized["outcome"]),
                policy_id=str(normalized.get("policy_id") or POLICY_ID_DEFAULT),
                policy_version=str(normalized.get("policy_version") or POLICY_VERSION_DEFAULT),
                reason_codes=list(normalized.get("reason_codes") or []),
                evidence_json=normalized.get("evidence_json"),
                duplicate_of=normalized.get("duplicate_of"),
                decided_at=str(normalized.get("decided_at") or now),
            )
            outcome = str(normalized["outcome"])
            if outcome == "rejected":
                counts["rejected"] += 1
            elif outcome == "failed":
                counts["failed"] += 1

        for raw in items:
            item_payload = normalize_item_payload(
                raw.to_payload() if hasattr(raw, "to_payload") else dict(raw)
            )
            item_payload.pop("_first_run_inherited", None)
            if not isinstance(item_payload.get("first_run_id"), str) or \
                    item_payload["first_run_id"] == "pending":
                item_payload["first_run_id"] = run_id
            item_id = item_payload["id"]
            decided = conn.execute(
                "SELECT outcome FROM admissions WHERE run_id = ? AND item_id = ?",
                (run_id, item_id),
            ).fetchone()
            if decided is not None:
                # Same (run_id, item_id) already decided in THIS run: the
                # ledger is append-only, so this is a pure no-op (precedence 0).
                continue
            existing = conn.execute(
                "SELECT id FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            if existing is not None:
                _append_admission(conn, run_id=run_id, item_id=item_id, outcome="rejected",
                                  policy_id=POLICY_ID_DEFAULT,
                                  policy_version=POLICY_VERSION_DEFAULT,
                                  reason_codes=["DUPLICATE_ID"], evidence_json=None,
                                  duplicate_of=str(existing["id"]), decided_at=now)
                counts["rejected"] += 1
                continue
            url_winner = conn.execute(
                "SELECT id FROM items WHERE url = ? AND state = 'accepted'",
                (item_payload["url"],),
            ).fetchone()
            if url_winner is not None:
                _append_admission(conn, run_id=run_id, item_id=item_id, outcome="rejected",
                                  policy_id=POLICY_ID_DEFAULT,
                                  policy_version=POLICY_VERSION_DEFAULT,
                                  reason_codes=["DUPLICATE_URL"], evidence_json=None,
                                  duplicate_of=str(url_winner["id"]), decided_at=now)
                counts["rejected"] += 1
                continue
            _persist_derived_fields(conn, item_payload)
            _insert_item(conn, item_payload)
            _append_admission(conn, run_id=run_id, item_id=item_id, outcome="accepted",
                              policy_id=POLICY_ID_DEFAULT, policy_version=POLICY_VERSION_DEFAULT,
                              reason_codes=["ACCEPTED"], evidence_json=None,
                              duplicate_of=None, decided_at=now)
            counts["accepted"] += 1
            counts["persisted"] += 1

        _check_run_invariants(conn, run_id)

        # Recompute durable counters from the ledger (honest accounting).
        by_outcome = dict(
            conn.execute(
                "SELECT outcome, COUNT(*) FROM admissions WHERE run_id = ? GROUP BY outcome",
                (run_id,),
            ).fetchall()
        )
        counts["accepted"] = int(by_outcome.get("accepted", 0))
        counts["rejected"] = int(by_outcome.get("rejected", 0))
        counts["failed"] = int(by_outcome.get("failed", 0))
        record_run_finish(conn, run_id, status=str(payload.get("status") or "success"),
                          counts=counts, invariant_ok=True,
                          config_hash=payload.get("config_hash"),
                          sources_json=(
                              json.dumps(payload["sources_json"], ensure_ascii=False)
                              if isinstance(payload.get("sources_json"), (dict, list))
                              else payload.get("sources_json")))
        duplicate_rows = int(conn.execute(
            "SELECT COUNT(*) FROM admissions WHERE run_id = ? AND duplicate_of IS NOT NULL",
            (run_id,),
        ).fetchone()[0])
        return {
            "run_id": run_id,
            "ledger": {
                "accepted": counts["accepted"],
                "rejected": counts["rejected"],
                "failed": counts["failed"],
            },
            "inserted": counts["persisted"],
            "duplicates": duplicate_rows,
            "superseded": 0,
            "invariant_ok": True,
        }


def _duplicate_count(conn: sqlite3.Connection, run_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM admissions WHERE run_id = ? AND duplicate_of IS NOT NULL",
        (run_id,),
    ).fetchone()
    return int(row[0])
