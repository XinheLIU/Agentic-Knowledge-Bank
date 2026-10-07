"""AssetStore facade and typed result objects for the canonical SQLite store.

Typed surface required by ticket 07: callers depend on :class:`AssetStore` and
dataclass results, not on raw sqlite3 rows. The store composes schema, writer,
reader, and FTS modules behind one object so consumers never touch a connection.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

__all__ = [
    "AdmissionRecord",
    "AssetStore",
    "ItemRecord",
    "ItemUpsertResult",
    "RunRecord",
    "RunIngestResult",
    "StoreStats",
    "connect",
    "project_version",
]


def project_version() -> str:
    """The single project version source (G6).

    Reads the installed ``ai-kb`` distribution version (declared once in
    ``pyproject.toml``). Every visible surface — UI sidebar, CLI banner, MCP
    ``knowledge_stats`` — must call this instead of hard-coding a literal.
    """
    try:
        return version("ai-kb")
    except PackageNotFoundError:  # pragma: no cover - bare checkout
        return "unknown"


@dataclass(frozen=True)
class ItemRecord:
    """One accepted-asset row (``items``), exposed read-only to consumers."""

    id: str
    state: str
    superseded_by: str | None
    source_type: str
    title: str
    url: str
    author: str | None
    published_at: str | None
    fetched_at: str
    story_fp: str
    profile: str | None
    profile_method: str | None
    profile_confidence: float | None
    profile_reason: str | None
    score: float | None
    score_reason: str | None
    summary: str | None
    content_main: str | None
    content_comments: str | None
    metadata_json: str | None
    first_seen_at: str
    first_run_id: str
    updated_at: str
    tags: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload = {k: v for k, v in self.__dict__.items() if k != "tags"}
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True)
class AdmissionRecord:
    """One append-only candidate decision (``admissions`` ledger row)."""

    run_id: str
    item_id: str
    outcome: str
    policy_id: str
    policy_version: str
    reason_codes: tuple[str, ...]
    evidence_json: str | None
    duplicate_of: str | None
    decided_at: str

    def to_payload(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True)
class RunRecord:
    """One ingestion run (``runs`` row)."""

    run_id: str
    radar: str
    radar_ref: str
    config_hash: str | None
    started_at: str
    finished_at: str | None
    status: str
    fetched: int
    mapped: int
    accepted: int
    rejected: int
    failed: int
    persisted: int
    invariant_ok: bool
    sources_json: str | None

    def to_payload(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["invariant_ok"] = bool(self.invariant_ok)
        return payload


@dataclass(frozen=True)
class ItemUpsertResult:
    """Idempotent item admission outcome (write-once semantics)."""

    inserted: int
    duplicates: int
    superseded: int = 0

    @property
    def persisted(self) -> int:
        return self.inserted


@dataclass(frozen=True)
class RunIngestResult:
    """Outcome of admitting one run's items under the canonical model."""

    run_id: str
    ledger: dict[str, int] = field(default_factory=dict)
    inserted: int = 0
    duplicates: int = 0
    superseded: int = 0
    invariant_ok: bool = True


@dataclass(frozen=True)
class StoreStats:
    """Whole-store counters (accepted assets only for items)."""

    item_count: int
    accepted_count: int
    superseded_count: int
    run_count: int
    admission_count: int
    tag_count: int

    def to_payload(self) -> dict[str, int]:
        return {
            "item_count": self.item_count,
            "accepted_count": self.accepted_count,
            "superseded_count": self.superseded_count,
            "run_count": self.run_count,
            "admission_count": self.admission_count,
            "tag_count": self.tag_count,
        }


# ---------------------------------------------------------------------------
# sibling modules
#
# Imported AFTER the dataclass definitions below: the facade composes
# schema/writer/reader/FTS/export, and those modules import these record
# types back, so defining the dataclasses first breaks the import cycle
# (``import kb.store.model`` as the first store import used to fail with a
# partial-module ImportError).
# ---------------------------------------------------------------------------

from kb.store import export as export_mod  # noqa: E402
from kb.store import fts as fts_mod  # noqa: E402
from kb.store import reader as reader_mod  # noqa: E402
from kb.store import schema as schema_mod  # noqa: E402
from kb.store import writer as writer_mod  # noqa: E402


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a raw sqlite3 connection with the store's PRAGMAs applied.

    ``sqlite3.Row`` row_factory is set so every reader can address columns
    by name consistently (tuples are never assumed).
    """
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class AssetStore:
    """Typed facade over the canonical SQLite asset store."""

    def __init__(self, conn: sqlite3.Connection, *, radar: str = "horizon") -> None:
        self._conn = conn
        self.radar = radar

    @classmethod
    def open(cls, path: str | Path = ":memory:", *, radar: str = "horizon") -> "AssetStore":
        """Open (creating/migrating) the store at ``path``."""
        conn = connect(path)
        schema_mod.migrate(conn)
        return cls(conn, radar=radar)

    @classmethod
    def in_memory(cls, *, radar: str = "horizon") -> "AssetStore":
        return cls.open(":memory:", radar=radar)

    # -- version (G6: one project version source) --------------------------
    @staticmethod
    def version() -> str:
        """Project version for visible surfaces; see :func:`project_version`."""
        return project_version()

    # -- writes ------------------------------------------------------------
    def ensure_run(self, run: RunRecord | Mapping[str, Any]) -> None:
        writer_mod.ensure_run(self._conn, run)

    def ensure_item(
        self,
        item: ItemRecord | Mapping[str, Any],
        *,
        run_id: str,
        policy_id: str = "admission-policy",
        policy_version: str = "0.1.0",
        evidence_json: str | None = None,
    ) -> ItemUpsertResult:
        return writer_mod.ensure_item(self._conn, item, run_id=run_id,
                                      policy_id=policy_id, policy_version=policy_version,
                                      evidence_json=evidence_json)

    def record_rejections(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        run_id: str,
        policy_id: str = "admission-policy",
        policy_version: str = "0.1.0",
    ) -> int:
        return writer_mod.record_rejections(self._conn, rows, run_id=run_id,
                                            policy_id=policy_id,
                                            policy_version=policy_version)

    def supersede_item(self, item_id: str, *, successor_id: str, run_id: str,
                       policy_id: str = "admission-policy",
                       policy_version: str = "0.1.0") -> bool:
        return writer_mod.supersede_item(
            self._conn, item_id, successor_id=successor_id, run_id=run_id,
            policy_id=policy_id, policy_version=policy_version,
        )

    def ingest_run(
        self,
        run: RunRecord | Mapping[str, Any],
        items: Sequence[ItemRecord | Mapping[str, Any]],
        rejections: Sequence[Mapping[str, Any]],
    ) -> RunIngestResult:
        return writer_mod.ingest_run(self._conn, run, items, rejections)

    # -- reads -------------------------------------------------------------
    def get_item(self, item_id: str, *, include_superseded: bool = False) -> ItemRecord | None:
        return reader_mod.get_item(self._conn, item_id, include_superseded=include_superseded)

    def list_items(self, *, q: str | None = None, source_type: str | None = None,
                   include_superseded: bool = False, limit: int | None = None) -> list[ItemRecord]:
        return reader_mod.list_items(self._conn, q=q, source_type=source_type,
                                     include_superseded=include_superseded, limit=limit)

    def search(self, q: str, *, source_type: str | None = None,
               include_superseded: bool = False, limit: int = 20) -> tuple[list[ItemRecord], str | None]:
        return fts_mod.search(self._conn, q, source_type=source_type,
                              include_superseded=include_superseded, limit=limit)

    def fts_mode(self) -> str:
        return fts_mod.fts_mode(self._conn)

    def get_run(self, run_id: str) -> RunRecord | None:
        return reader_mod.get_run(self._conn, run_id)

    def list_runs(self, *, limit: int | None = None) -> list[RunRecord]:
        return reader_mod.list_runs(self._conn, limit=limit)

    def get_admissions(self, item_id: str, *, run_id: str | None = None) -> list[AdmissionRecord]:
        return reader_mod.get_admissions(self._conn, item_id, run_id=run_id)

    def audit_admissions(self, *, run_id: str | None = None, outcome: str | None = None,
                         limit: int | None = None) -> list[AdmissionRecord]:
        return reader_mod.audit_admissions(self._conn, run_id=run_id, outcome=outcome, limit=limit)

    def stats(self) -> StoreStats:
        return reader_mod.stats(self._conn)

    def latest_published_day(self) -> str | None:
        return reader_mod.latest_published_day(self._conn)

    def story_edges(self, item_id: str) -> list[dict[str, Any]]:
        return reader_mod.story_edges(self._conn, item_id)

    # -- export / backup / restore ------------------------------------------
    def export_jsonl(self, output_path: str | Path, *,
                     include_audit: bool = False) -> dict[str, Any]:
        return export_mod.export_jsonl(self._conn, output_path, include_audit=include_audit)

    def backup(self, backup_path: str | Path) -> dict[str, Any]:
        return export_mod.backup(self._conn, backup_path)

    def restore_jsonl(self, input_path: str | Path, *, radar: str | None = None) -> dict[str, Any]:
        return export_mod.restore_jsonl(self._conn, input_path, radar=radar or self.radar)

    def restore_from_backup(self, backup_path: str | Path, *,
                            target_path: str | Path) -> dict[str, Any]:
        return export_mod.restore_from_backup(backup_path, target_path)

    # -- schema helpers ------------------------------------------------------
    def schema_version(self) -> int:
        return schema_mod.schema_version(self._conn)

    def verify_schema(self) -> bool:
        return schema_mod.verify_schema(self._conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "AssetStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def iter_payloads(records: Sequence[ItemRecord | Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Normalize ItemRecord/Mapping inputs to plain payload dicts."""
    for record in records:
        yield record.to_payload() if isinstance(record, ItemRecord) else dict(record)
