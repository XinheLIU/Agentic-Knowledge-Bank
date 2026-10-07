"""Versioned, transactional, repeatable schema migrations (ticket 07).

Canonical DDL per the resolved asset model (ticket 02, ``asset-audit-model.md``
§6). All enum CHECK lists are **generated** from ``kb/model.py`` constants at
migration time — never copied (asset model §4, closes O2). ``items`` and
``runs`` supersede design.md §2; ``admissions`` is added; ``tags``, artifacts,
``edges`` and FTS follow design.md §2.

Migration protocol: each step runs inside one transaction (``BEGIN
IMMEDIATE`` … ``COMMIT``) recorded in ``schema_migrations(version, applied_at,
description)``; ``migrate()`` is repeatable (idempotent — applied steps are
skipped) and safe under concurrent writers (SQLite serializes write
transactions; a second caller re-reads the applied set on retry).
"""

from __future__ import annotations

import sqlite3
import time

from kb import model as kb_model

__all__ = [
    "SCHEMA_VERSION",
    "MigrationError",
    "migrate",
    "schema_version",
    "verify_schema",
    "applied_versions",
    "generated_check",
]

#: Highest known schema version; bumped by appending a migration step.
SCHEMA_VERSION = 1


class MigrationError(RuntimeError):
    """A migration step failed; the transaction was rolled back."""


def generated_check(column: str, values: tuple[str, ...]) -> str:
    """Render a CHECK constraint from a ``kb/model.py`` vocabulary.

    The single owner of each vocabulary is ``kb/model.py``; DDL never
    hard-codes the literals (asset model §4).
    """
    joined = ", ".join(f"'{v}'" for v in values)
    return f"CHECK ({column} IN ({joined}))"


def _v1_items() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS items (
  id                 TEXT PRIMARY KEY,
  state              TEXT NOT NULL {generated_check('state', kb_model.ASSET_STATES)},
  superseded_by      TEXT REFERENCES items(id) DEFERRABLE INITIALLY DEFERRED,
  source_type        TEXT NOT NULL,
  title              TEXT NOT NULL,
  url                TEXT NOT NULL,
  author             TEXT,
  published_at       TEXT,
  fetched_at         TEXT NOT NULL,
  story_fp           TEXT,
  profile            TEXT,
  profile_method     TEXT,
  profile_confidence REAL,
  profile_reason     TEXT,
  score              REAL,
  score_reason       TEXT,
  summary            TEXT,
  content_main       TEXT,
  content_comments   TEXT,
  metadata_json      TEXT,
  first_seen_at      TEXT NOT NULL,
  first_run_id       TEXT NOT NULL REFERENCES runs(run_id),
  updated_at         TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_url   ON items(url) WHERE state = 'accepted';
CREATE INDEX IF NOT EXISTS idx_items_story ON items(story_fp);
CREATE INDEX IF NOT EXISTS idx_items_state ON items(state);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_score     ON items(score DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source_type);
"""


def _v1_admissions() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS admissions (
  run_id         TEXT NOT NULL REFERENCES runs(run_id),
  item_id        TEXT NOT NULL,
  outcome        TEXT NOT NULL {generated_check('outcome', kb_model.OUTCOMES)},
  policy_id      TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  reason_codes   TEXT NOT NULL,
  evidence_json  TEXT,
  duplicate_of   TEXT,
  decided_at     TEXT NOT NULL,
  PRIMARY KEY (run_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_admissions_item ON admissions(item_id);
"""


def _v1_runs() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS runs (
  run_id       TEXT PRIMARY KEY,
  radar        TEXT NOT NULL,
  radar_ref    TEXT NOT NULL,
  config_hash  TEXT,
  started_at   TEXT NOT NULL,
  finished_at  TEXT,
  status       TEXT NOT NULL {generated_check('status', kb_model.RUN_STATUSES)},
  fetched      INTEGER NOT NULL DEFAULT 0,
  mapped       INTEGER NOT NULL DEFAULT 0,
  accepted     INTEGER NOT NULL DEFAULT 0,
  rejected     INTEGER NOT NULL DEFAULT 0,
  failed       INTEGER NOT NULL DEFAULT 0,
  persisted    INTEGER NOT NULL DEFAULT 0,
  invariant_ok INTEGER NOT NULL DEFAULT 1,
  sources_json TEXT
);
"""


def _v1_tags() -> str:
    return """
CREATE TABLE IF NOT EXISTS tags (
  item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  tag     TEXT NOT NULL,
  PRIMARY KEY (item_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
"""


def _v1_artifacts() -> str:
    return """
CREATE TABLE IF NOT EXISTS artifacts (
  item_id  TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  language TEXT NOT NULL,
  title    TEXT,
  PRIMARY KEY (item_id, language)
);

CREATE TABLE IF NOT EXISTS artifact_blocks (
  item_id    TEXT NOT NULL,
  language   TEXT NOT NULL,
  block_id   TEXT NOT NULL,
  title      TEXT,
  content    TEXT,
  is_primary INTEGER DEFAULT 0,
  position   INTEGER,
  PRIMARY KEY (item_id, language, block_id),
  FOREIGN KEY (item_id, language) REFERENCES artifacts(item_id, language) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifact_sources (
  item_id   TEXT NOT NULL,
  language  TEXT NOT NULL,
  source_id TEXT NOT NULL,
  title     TEXT,
  url       TEXT,
  PRIMARY KEY (item_id, language, source_id),
  FOREIGN KEY (item_id, language) REFERENCES artifacts(item_id, language) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS block_source_refs (
  item_id   TEXT NOT NULL,
  language  TEXT NOT NULL,
  block_id  TEXT NOT NULL,
  source_id TEXT NOT NULL,
  PRIMARY KEY (item_id, language, block_id, source_id)
);
"""


def _v1_edges() -> str:
    return """
CREATE TABLE IF NOT EXISTS edges (
  src_id     TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  dst_id     TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  weight     REAL,
  created_at TEXT,
  PRIMARY KEY (src_id, dst_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id, kind);
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind);
"""


def _v1_meta() -> str:
    return """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     INTEGER PRIMARY KEY,
  applied_at  TEXT NOT NULL,
  description TEXT NOT NULL
);
"""


def _split_statements(block: str) -> tuple[str, ...]:
    """Split a multi-statement DDL block into individual statements.

    DDL here never contains semicolons inside string literals, so a plain
    split is safe; blank statements are dropped.
    """
    return tuple(
        statement.strip()
        for statement in block.split(";")
        if statement.strip()
    )


#: Ordered migration steps: ``(version, description, DDL statements)``.
MIGRATIONS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (1, "canonical asset store baseline",
     _split_statements("\n".join((
         _v1_meta(), _v1_runs(), _v1_items(), _v1_admissions(), _v1_tags(),
         _v1_artifacts(), _v1_edges(),
     )))),
)


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Versions recorded in ``schema_migrations`` (empty before first step)."""
    try:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {int(row[0]) for row in rows}


def schema_version(conn: sqlite3.Connection) -> int:
    """Current persisted schema version (0 = not yet migrated)."""
    versions = applied_versions(conn)
    return max(versions) if versions else 0


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations; repeatable and transactional.

    Each step executes its DDL inside one write transaction and records the
    version in ``schema_migrations`` — applied steps are skipped, so re-running
    is a no-op. PRAGMAs are set first; foreign keys are ON so the declared
    model FKs are enforced. A ``sqlite3.Row`` row factory is installed when
    the caller has not set one, so readers address columns by name.
    """
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")

    applied = applied_versions(conn)
    current = schema_version(conn)
    for version, description, statements in MIGRATIONS:
        if version in applied:
            continue
        if version != current + 1:
            raise MigrationError(
                f"migration {version} cannot follow schema version {current}"
            )
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at, description) "
                "VALUES (?, ?, ?)",
                (version, _utcnow(), description),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise MigrationError(f"migration {version} failed: {exc}") from exc
        current = version
    return current


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _expected_tables() -> dict[str, set[str]]:
    """Canonical table → column expectations asserted by ``verify_schema``."""
    return {
        "items": {
            "id", "state", "superseded_by", "source_type", "title", "url",
            "author", "published_at", "fetched_at", "story_fp", "profile",
            "profile_method", "profile_confidence", "profile_reason", "score",
            "score_reason", "summary", "content_main", "content_comments",
            "metadata_json", "first_seen_at", "first_run_id", "updated_at",
        },
        "admissions": {
            "run_id", "item_id", "outcome", "policy_id", "policy_version",
            "reason_codes", "evidence_json", "duplicate_of", "decided_at",
        },
        "runs": {
            "run_id", "radar", "radar_ref", "config_hash", "started_at",
            "finished_at", "status", "fetched", "mapped", "accepted",
            "rejected", "failed", "persisted", "invariant_ok", "sources_json",
        },
        "tags": {"item_id", "tag"},
        "artifacts": {"item_id", "language", "title"},
        "artifact_blocks": {
            "item_id", "language", "block_id", "title", "content",
            "is_primary", "position",
        },
        "artifact_sources": {
            "item_id", "language", "source_id", "title", "url",
        },
        "block_source_refs": {
            "item_id", "language", "block_id", "source_id",
        },
        "edges": {"src_id", "dst_id", "kind", "weight", "created_at"},
        "schema_migrations": {"version", "applied_at", "description"},
    }


def _expected_indexes() -> set[str]:
    return {
        "idx_items_url", "idx_items_story", "idx_items_state",
        "idx_items_published", "idx_items_score", "idx_items_source",
        "idx_admissions_item", "idx_tags_tag", "idx_edges_dst", "idx_edges_kind",
    }


def verify_schema(conn: sqlite3.Connection) -> bool:
    """True when every canonical table/index exists with expected columns."""
    tables: dict[str, set[str]] = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ):
        columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})")}
        tables[name] = columns
    for table, expected in _expected_tables().items():
        if table not in tables or not expected.issubset(tables[table]):
            return False
    indexes = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    return _expected_indexes().issubset(indexes)


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Column names of ``table`` (helper for migration tests)."""
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def index_names(conn: sqlite3.Connection) -> set[str]:
    """All index names on the schema (helper for migration tests)."""
    return {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }


def fts_installed(conn: sqlite3.Connection) -> bool:
    """True when SQLite was built with FTS5 (probe via in-memory table)."""
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_probe USING fts5(x)")
    except sqlite3.OperationalError:
        return False
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS temp.fts5_probe")
        except sqlite3.Error:  # pragma: no cover - drop of a fresh temp table
            pass
    return True
