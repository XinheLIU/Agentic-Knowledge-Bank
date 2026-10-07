"""UI/source-controls seam on the canonical SQLite asset store (ticket 12).

Migration notes (legacy → canonical):

- Every endpoint goes through :class:`kb.store.model.AssetStore` (or Horizon
  source governance below); no endpoint scans or mutates retired legacy JSON.
- ``kb serve-ui`` is the run boundary: :func:`main` is invoked by
  ``kb serve-ui`` / ``python ui/app.py``.
- Superseded assets are hidden by default (accepted-only read surface, I4);
  supersede/audit visibility arrives with the operator workbench (P1).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from flask import Flask, jsonify, request
from flask_cors import CORS

from agent_tools.horizon import source_config
from kb.paths import data_root
from kb.store.model import AssetStore, ItemRecord, project_version

__all__ = ["create_app", "main", "DEFAULT_DB_PATH"]

#: Repo-root default for the canonical store file (design.md D-1: SQLite at
#: ``knowledge/kb.sqlite``); tests override via :func:`create_app`.
DEFAULT_DB_PATH = data_root() / "kb.sqlite"

ALLOWED_SORT = ("updated_at", "published_at", "score", "title")

#: UI-facing derived states (assets are durable; superseded → "archived").
UI_STATUSES = ("published", "archived")

_FTS_UNSAFE = re.compile(r'["*()]')

#: Upper bound for one retrieval pull before in-Python filtering/pagination.
_MAX_PULL = 500


def _clean_fts_query(q: str) -> str:
    """Quote the raw query as an FTS5 phrase so operator input stays data.

    Trigram tokenization makes plain keywords degrade to substring scanning
    anyway; quoting sidesteps FTS5 syntax errors on punctuation. The LIKE
    fallback mode ignores FTS queries entirely, so no special handling there.
    """
    safe = _FTS_UNSAFE.sub(" ", q).strip()
    if not safe:
        return ""
    return '"' + safe.replace('"', " ") + '"'


def _canonical_row(rec: ItemRecord) -> dict[str, Any]:
    """Project an ItemRecord to the UI's canonical item payload (no legacy
    personalization fields — R-D7: those columns do not exist in this schema).
    """
    metadata: dict[str, Any] = {}
    if rec.metadata_json:
        try:
            loaded = json.loads(rec.metadata_json)
            if isinstance(loaded, dict):
                metadata = loaded
        except ValueError:
            metadata = {}
    artifacts = metadata.get("artifacts") or []
    localized = {a.get("language"): a for a in artifacts if isinstance(a, dict)}
    return {
        "id": rec.id,
        "title": rec.title,
        "source_type": rec.source_type,
        "url": rec.url,
        "author": rec.author,
        "published_at": rec.published_at,
        "fetched_at": rec.fetched_at,
        "profile": rec.profile,
        "profile_confidence": rec.profile_confidence,
        "score": rec.score,
        "score_reason": rec.score_reason,
        "summary": rec.summary,
        "content_main": rec.content_main,
        "tags": list(rec.tags),
        "artifacts": artifacts,
        "has_zh": "zh" in localized,
        "has_en": "en" in localized,
        "first_seen_at": rec.first_seen_at,
        "first_run_id": rec.first_run_id,
        "updated_at": rec.updated_at,
        "state": rec.state,
    }


def create_app(
    store: AssetStore | None = None,
    *,
    db_path: str | Path | None = None,
    horizon_dir: str | Path | None = None,
) -> Flask:
    """Application factory (browser-level tests build an isolated app).

    ``store`` wins over ``db_path``; with neither, the canonical store file
    at ``DEFAULT_DB_PATH`` is opened (creating/migrating as needed).
    """
    if store is None:
        store = AssetStore.open(db_path or DEFAULT_DB_PATH)
    app = Flask(__name__)
    CORS(app)
    app.config["STORE"] = store

    # ------------------------------------------------------------------
    # errors: 404 unknown id, 400 bad request, 500 store failure (五态: Error)
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def _not_found(_err):  # pragma: no cover - flask handles body
        return jsonify({"error": "Not found"}), 404

    def _not_found_response() -> tuple[Any, int]:
        return jsonify({"error": "Not found"}), 404

    def _bad_request(msg: str) -> tuple[Any, int]:
        return jsonify({"error": msg}), 400

    # ------------------------------------------------------------------
    # items
    # ------------------------------------------------------------------

    def _query_items(
        *,
        q: str,
        source_type: str,
        tag: str,
        status: str,
        from_date: str,
        to_date: str,
        sort: str,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Shared list/search used by /api/articles and /api/filters."""
        items: list[ItemRecord]
        if q:
            # Bounded retrieval (single-operator UI); bm25 ranks relevance
            # first, recency/time filters refine in Python below. The FTS
            # phrase-quoting only applies when FTS serves the query; the
            # LIKE fallback receives the raw lowered text.
            cleaned = (_clean_fts_query(q)
                       if store.fts_mode() == "fts5-trigram" else q.lower())
            items, mode = store.search(
                cleaned, source_type=source_type or None, limit=_MAX_PULL
            )
            app.config["last_fts_mode"] = mode
        else:
            items = store.list_items(source_type=source_type or None, limit=_MAX_PULL)
        if tag:
            items = [i for i in items if tag in i.tags]
        if status:
            items = [i for i in items if _derive_ui_status(i) == status]
        if from_date:
            items = [i for i in items if (i.updated_at or "") >= from_date]
        if to_date:
            items = [i for i in items if (i.updated_at or "")[:10] <= to_date]
        items.sort(key=_sort_key(sort), reverse=sort in ("updated_at", "published_at", "score"))
        total = len(items)
        start = (page - 1) * limit
        return [_canonical_row(i) for i in items[start:start + limit]], total

    @app.get("/api/articles")
    def list_articles():
        args = request.args
        q = (args.get("q") or "").strip()
        source_type = (args.get("source_type") or "").strip()
        tag = (args.get("tag") or "").strip()
        status = (args.get("status") or "").strip()
        from_date = (args.get("from_date") or "").strip()
        to_date = (args.get("to_date") or "").strip()
        sort = args.get("sort", "updated_at")
        if sort not in ALLOWED_SORT:
            return _bad_request(f"unknown sort {sort!r}")
        page = args.get("page", 1, type=int) or 1
        limit = args.get("limit", 20, type=int) or 20
        page = max(1, page)
        limit = min(100, max(1, limit))
        rows, total = _query_items(
            q=q, source_type=source_type, tag=tag, status=status,
            from_date=from_date, to_date=to_date, sort=sort, page=page, limit=limit,
        )
        return jsonify({
            "items": rows,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": max(1, math.ceil(total / limit)),
        })

    @app.get("/api/articles/<path:item_id>")
    def get_article(item_id: str):
        rec = store.get_item(item_id)
        if rec is None:
            return _not_found_response()
        return jsonify(_canonical_row(rec))

    # Explicitly refuse state-mutating writes: assets are write-once
    # (asset-audit-model §5); edits/deletes become supersede/audit work (P1).
    @app.route("/api/articles/<path:item_id>", methods=["PATCH", "PUT", "DELETE"])
    def mutate_article(item_id: str):
        if store.get_item(item_id) is None:
            return _not_found_response()
        return _bad_request(
            "assets are write-once; mutation endpoints are not part of the "
            "canonical read surface"
        )

    @app.post("/api/articles/batch")
    def batch_operation():
        payload = request.get_json(silent=True) or {}
        action = payload.get("action", "")
        if action == "delete":
            return _bad_request("delete is not a canonical batch action")
        return _bad_request(
            "assets are write-once; batch mutations are not part of the "
            "canonical read surface"
        )

    @app.post("/api/articles/export")
    def export_articles():
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids") or []
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            return _bad_request("ids must be a non-empty string array")
        articles = []
        for item_id in ids:
            rec = store.get_item(item_id)
            if rec is not None:
                articles.append(_canonical_row(rec))
        return jsonify({"articles": articles, "count": len(articles)})

    @app.post("/api/articles/import")
    def import_articles():
        return _bad_request(
            "import is served by 'kb ingest' (admission ledger) and "
            "'kb restore' (JSONL replay), not the UI"
        )

    @app.post("/api/articles/import-legacy")
    def import_legacy_articles():
        payload = request.get_json(silent=True) or {}
        articles = payload.get("articles")
        if not isinstance(articles, list) or not articles:
            return _bad_request("articles must be a non-empty array")
        if payload.get("confirm") is not True:
            return _bad_request(
                "legacy import replaces importArticles; pass confirm:true to proceed"
            )
        result = _import_legacy_rows(store, articles, run_id=str(payload.get("run_id") or "ui-legacy-import"))
        status = 200 if result["failed"] == 0 else 207
        return jsonify(result), status

    @app.get("/api/stats")
    def get_stats():
        articles = store.list_items(limit=None)
        rows = [_canonical_row(a) for a in articles]
        sources: dict[str, int] = {}
        tags: dict[str, int] = {}
        statuses: dict[str, int] = {}
        profiles: dict[str, int] = {}
        for row in rows:
            sources[row["source_type"]] = sources.get(row["source_type"], 0) + 1
            for t in row["tags"]:
                tags[t] = tags.get(t, 0) + 1
            statuses[row["state"]] = statuses.get(row["state"], 0) + 1
            if row["profile"]:
                profiles[row["profile"]] = profiles.get(row["profile"], 0) + 1
        runs = store.list_runs(limit=10)
        return jsonify({
            "version": project_version(),
            "total": len(rows),
            "sources": sources,
            "tags": tags,
            "statuses": statuses,
            "profiles": profiles,
            "runs": [r.to_payload() | {"sources": _load_sources_json(r.sources_json)} for r in runs],
            "fts_mode": store.fts_mode(),
        })

    @app.get("/api/filters")
    def get_filters():
        rows = [_canonical_row(a) for a in store.list_items(limit=None)]
        sources = sorted({r["source_type"] for r in rows})
        tags = sorted({t for r in rows for t in r["tags"]})
        profiles = sorted({r["profile"] for r in rows if r["profile"]})
        return jsonify({
            "sources": sources,
            "tags": tags,
            "profiles": profiles,
            "statuses": sorted(UI_STATUSES),
            "sorts": list(ALLOWED_SORT),
        })

    # ------------------------------------------------------------------
    # Horizon source governance (enable/disable with config validation)
    # ------------------------------------------------------------------

    @app.get("/api/sources")
    def list_sources():
        try:
            sources = source_config.load_sources(horizon_dir)
        except source_config.ConfigError as exc:
            return jsonify({"error": str(exc)}), 500
        counts = _recent_counts_by_source(store, days=7)
        for src in sources:
            src["last_7d_count"] = counts.get(src["slug"], 0)
        return jsonify({
            "sources": sources,
            "horizon_dir": str(source_config.horizon_dir(horizon_dir)),
        })

    @app.patch("/api/sources/<slug>")
    def patch_source(slug: str):
        payload = request.get_json(silent=True) or {}
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            return _bad_request("body must be {'enabled': boolean}")
        try:
            source_config.set_source_enabled(slug, enabled, horizon_dir)
        except source_config.ConfigError as exc:
            # validation failures reported explicitly; config stays untouched
            return jsonify({"error": str(exc)}), 400
        sources = source_config.load_sources(horizon_dir)
        counts = _recent_counts_by_source(store, days=7)
        for src in sources:
            src["last_7d_count"] = counts.get(src["slug"], 0)
        return jsonify({"sources": sources})

    # ------------------------------------------------------------------
    # SPA + version (G6: one project version source)
    # ------------------------------------------------------------------

    @app.get("/api/version")
    def get_version():
        return jsonify({"version": project_version()})

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/healthz")
    def healthz():
        try:
            store.stats()
        except sqlite3.Error as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "version": project_version()})

    return app


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _sort_key(sort: str):
    if sort == "title":
        return lambda r: (r.title or "").lower()
    if sort == "score":
        return lambda r: (r.score is not None, r.score or 0.0)
    return lambda r: getattr(r, sort) or ""


def _load_sources_json(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def _derive_ui_status(rec: ItemRecord) -> str:
    """UI status derived from canonical columns (no legacy status field).

    Admitted assets are durable by definition; the UI exposes the
    supersede-relevant projection without pretending a legacy edit-state.
    """
    if rec.state == "superseded":
        return "archived"
    return "published"


def _recent_counts_by_source(store: AssetStore, *, days: int = 7) -> dict[str, int]:
    """Per-source_type count of recently fetched assets (UI 近7天 column)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    counts: dict[str, int] = {}
    for rec in store.list_items(limit=None):
        if (rec.fetched_at or "") >= cutoff:
            counts[rec.source_type] = counts.get(rec.source_type, 0) + 1
    return counts


def _import_legacy_rows(
    store: AssetStore, rows: Iterable[Mapping[str, Any]], *, run_id: str
) -> dict[str, int]:
    """Admit legacy-JSON rows through the canonical ingest path.

    Used by the cutover rehearsal (ticket 14) and the explicit
    ``/api/articles/import-legacy`` bridge: rows become candidates admitted
    under ``radar='legacy'``; the ledger keeps per-item decisions. Malformed
    rows are counted ``failed``, never silently dropped.
    """
    items: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    failed = 0
    for idx, row in enumerate(rows):
        item_id = row.get("id")
        url = row.get("source_url") or row.get("url")
        title = row.get("title")
        if not (isinstance(item_id, str) and item_id.strip()
                and isinstance(url, str) and url.strip()
                and isinstance(title, str) and title.strip()):
            rejections.append({
                "item_id": f"legacy:malformed:{idx}",
                "outcome": "failed",
                "reason_codes": ["MALFORMED_METADATA"],
            })
            failed += 1
            continue
        legacy_id = item_id if item_id.startswith("legacy:") else f"legacy:{item_id}"
        items.append({
            "id": legacy_id,
            "source_type": row.get("source_type") or "unknown",
            "title": title,
            "url": url,
            "author": row.get("author"),
            "published_at": row.get("published_at"),
            "fetched_at": row.get("collected_at") or _utcnow(),
            "summary": row.get("summary"),
            "score": row.get("score"),
            "tags": row.get("tags") or [],
            "metadata_json": {
                k: row[k]
                for k in ("audience", "category", "key_insight", "relevance_score", "source")
                if row.get(k) not in (None, "")
            } or None,
            "state": "accepted",
        })
    result = store.ingest_run(
        {"run_id": run_id, "radar": "legacy", "radar_ref": "ui-import", "status": "success"},
        items, rejections,
    )
    return {
        "imported": result["inserted"],
        "failed": failed,
        "duplicates": result["duplicates"] - failed,
        "skipped": failed + (result["duplicates"] - failed),
    }


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv: list[str] | None = None) -> int:
    """``kb serve-ui`` entrypoint (invoked by ``kb serve-ui`` or ``python ui/app.py``)."""
    parser = argparse.ArgumentParser(prog="serve-ui", description="Flask UI on the canonical store")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="asset store path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--horizon-dir", default=None, help="Horizon checkout dir override")
    args = parser.parse_args(argv)

    app = create_app(db_path=args.db, horizon_dir=args.horizon_dir)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
