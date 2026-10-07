"""FTS5 search with CJK tokenizer probe and an explicit tested fallback (ticket 07).

design.md §2 requires CJK-capable full-text search: the library mixes English
sources with Chinese summaries. ``trigram`` handles CJK substring matching;
older SQLite builds (or custom builds without FTS5) must degrade to an explicit,
logged ``LIKE`` fallback — never a silent one. The active mode is persisted in
the ``kb_fts_meta`` table so every consumer can assert which mode serves reads.

Modes:
- ``fts5-trigram`` — FTS5 table with ``tokenize='trigram'``.
- ``like-fallback`` — explicit fallback; ``search()`` routes to ``list_items``.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from kb.store import reader as reader_mod

if TYPE_CHECKING:  # pragma: no cover - typing only, breaks the import cycle
    from kb.store.model import ItemRecord

__all__ = [
    "FTS_TRIGRAM",
    "FTS_LIKE_FALLBACK",
    "probe_cjk_support",
    "install",
    "fts_mode",
    "search",
    "rebuild",
]

FTS_TRIGRAM = "fts5-trigram"
FTS_LIKE_FALLBACK = "like-fallback"

_FTS_TABLE = "items_fts"
_META_TABLE = "kb_fts_meta"
_TRIGGER_ITEMS = "items_fts_ai"
_TRIGGER_TAGS = "tags_fts_ai"


def _trigram_available(conn: sqlite3.Connection) -> bool:
    """Probe that FTS5 exists AND the trigram tokenizer accepts CJK text.

    The probe inserts CJK text into a temporary trigram table and reads it
    back through a MATCH query. Trigram tokens are three characters, so the
    probe query uses a quoted three-character CJK string (a two-character
    query cannot match under trigram semantics and would falsely report
    non-support). A build without trigram support fails the CREATE or the
    MATCH rather than silently degrading.
    """
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(t, tokenize='trigram')")
        conn.execute("INSERT INTO temp.fts_probe(t) VALUES ('中文检索测试')")
        hit = conn.execute(
            "SELECT COUNT(*) FROM temp.fts_probe WHERE t MATCH ?", ('"中文检"',)
        ).fetchone()[0]
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS temp.fts_probe")
        except sqlite3.Error:  # pragma: no cover - probe cleanup
            pass
    return int(hit) > 0


def probe_cjk_support(conn: sqlite3.Connection) -> bool:
    """Public startup probe: True when FTS5 trigram handles CJK queries."""
    return _trigram_available(conn)


def install(conn: sqlite3.Connection) -> str:
    """Create (or keep) the FTS index appropriate for this SQLite build.

    Probes CJK support at startup; when unavailable, records the explicit
    ``like-fallback`` mode (design.md §2: the degradation must be visible,
    never silent). Idempotent: an installed index matching the probe result
    is kept as-is. Uses the shared savepoint-safe transaction helper so it
    composes with caller-open transactions. Returns the active mode string.
    """
    from kb.store.writer import _write_txn

    with _write_txn(conn):
        meta_row = conn.execute(
            f"SELECT mode FROM {_META_TABLE} WHERE id = 1"
        ).fetchall() if _meta_exists(conn) else []
        has_fts = _fts_exists(conn)
        if _trigram_available(conn):
            mode = FTS_TRIGRAM
            if not has_fts:
                conn.execute("DROP TRIGGER IF EXISTS items_fts_ai")
                conn.execute(f"DROP TABLE IF EXISTS {_FTS_TABLE}")
                conn.execute(
                    f"""
                    CREATE VIRTUAL TABLE {_FTS_TABLE} USING fts5(
                      title, summary, content_main, content_comments,
                      content='items', content_rowid='rowid',
                      tokenize='trigram'
                    )
                    """
                )
                conn.execute(
                    f"""
                    CREATE TRIGGER {_TRIGGER_ITEMS} AFTER INSERT ON items BEGIN
                      INSERT INTO {_FTS_TABLE}(rowid, title, summary, content_main, content_comments)
                      VALUES (new.rowid, new.title, new.summary, new.content_main, new.content_comments);
                    END
                    """
                )
        else:
            mode = FTS_LIKE_FALLBACK
            conn.execute(f"DROP TABLE IF EXISTS {_FTS_TABLE}")
            conn.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_ITEMS}")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_META_TABLE} (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              mode TEXT NOT NULL
            )
            """
        )
        if meta_row:
            conn.execute(f"UPDATE {_META_TABLE} SET mode = ? WHERE id = 1", (mode,))
        else:
            conn.execute(f"INSERT INTO {_META_TABLE} (id, mode) VALUES (1, ?)", (mode,))
        _backfill(conn, mode)
        return mode


def _meta_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_META_TABLE,)
    ).fetchone()
    return row is not None


def _fts_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_FTS_TABLE,)
    ).fetchone()
    return row is not None


def _backfill(conn: sqlite3.Connection, mode: str) -> None:
    """Populate the index from existing items (no-op in like-fallback mode)."""
    if mode != FTS_TRIGRAM:
        return
    conn.execute(f"INSERT INTO {_FTS_TABLE}({_FTS_TABLE}) VALUES('rebuild')")


def fts_mode(conn: sqlite3.Connection) -> str:
    """Active retrieval mode; ``like-fallback`` after explicit degradation."""
    if not _meta_exists(conn):
        return FTS_LIKE_FALLBACK
    row = conn.execute(f"SELECT mode FROM {_META_TABLE} WHERE id = 1").fetchone()
    return str(row[0]) if row else FTS_LIKE_FALLBACK


def search(
    conn: sqlite3.Connection,
    q: str,
    *,
    source_type: str | None = None,
    include_superseded: bool = False,
    limit: int = 20,
) -> tuple[list["ItemRecord"], str | None]:
    """Full-text keyword search over accepted assets.

    Returns ``(items, mode)`` where ``mode`` records which retrieval path
    served the query (``fts5-trigram`` or ``like-fallback``) so callers can
    surface the degradation explicitly.
    """
    mode = fts_mode(conn)
    if mode != FTS_TRIGRAM or not _fts_exists(conn):
        items = reader_mod.list_items(
            conn, q=q, source_type=source_type,
            include_superseded=include_superseded, limit=limit,
        )
        return items, FTS_LIKE_FALLBACK

    clauses = ["items_fts MATCH ?"]
    params: list[Any] = [q]
    if not include_superseded:
        clauses.append("items.state = 'accepted'")
    if source_type is not None:
        clauses.append("items.source_type = ?")
        params.append(source_type)
    # bm25() ranks; lower is better in SQLite FTS5, so order ascending.
    sql = f"""
    SELECT items.id, items.state, items.superseded_by, items.source_type,
           items.title, items.url, items.author, items.published_at,
           items.fetched_at, items.story_fp, items.profile,
           items.profile_method, items.profile_confidence, items.profile_reason,
           items.score, items.score_reason, items.summary, items.content_main,
           items.content_comments, items.metadata_json, items.first_seen_at,
           items.first_run_id, items.updated_at
    FROM items_fts
    JOIN items ON items.rowid = items_fts.rowid
    WHERE {' AND '.join(clauses)}
    ORDER BY bm25(items_fts), items.published_at DESC
    LIMIT ?
    """
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    ids = [str(row["id"]) for row in rows]
    tags: dict[str, tuple[str, ...]] = {item_id: () for item_id in ids}
    if ids:
        placeholders = ", ".join("?" for _ in ids)
        for item_id, tag in conn.execute(
            f"SELECT item_id, tag FROM tags WHERE item_id IN ({placeholders}) ORDER BY tag",
            ids,
        ):
            tags[str(item_id)] += (str(tag),)
    items = [reader_mod._row_to_item(row, tags[str(row["id"])]) for row in rows]
    return items, FTS_TRIGRAM


def rebuild(conn: sqlite3.Connection) -> None:
    """Rebuild the FTS index from ``items`` (no-op in like-fallback mode)."""
    if fts_mode(conn) != FTS_TRIGRAM or not _fts_exists(conn):
        return
    conn.execute(f"INSERT INTO {_FTS_TABLE}({_FTS_TABLE}) VALUES('rebuild')")
