"""
AI Knowledge Base UI - Flask Backend
Reads/writes knowledge/articles/*.json directly.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge" / "articles"
INDEX_PATH = KNOWLEDGE_DIR / "index.json"
RSS_CONFIG = Path(__file__).resolve().parent.parent / "workflows" / "rss_sources.yaml"


class ArticleStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self._cache: dict[str, dict] | None = None
        self._mtime = 0.0

    def _is_cache_valid(self) -> bool:
        if not self.directory.exists():
            return False
        current_mtime = max(
            (f.stat().st_mtime for f in self.directory.glob("*.json") if f.name != "index.json"),
            default=0.0,
        )
        return self._cache is not None and current_mtime <= self._mtime

    def _load_all(self) -> dict[str, dict]:
        if self._is_cache_valid():
            return self._cache  # type: ignore[return-value]

        articles: dict[str, dict] = {}
        for path in self.directory.glob("*.json"):
            if path.name == "index.json":
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "id" in data:
                    articles[data["id"]] = data
            except (json.JSONDecodeError, OSError):
                continue

        self._cache = articles
        self._mtime = max(
            (f.stat().st_mtime for f in self.directory.glob("*.json") if f.name != "index.json"),
            default=0.0,
        )
        return articles

    def _write(self, article_id: str, data: dict) -> None:
        path = self._path_for(article_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = None  # invalidate cache

    def _delete(self, article_id: str) -> None:
        path = self._path_for(article_id)
        if path.exists():
            path.unlink()
        self._cache = None

    def _path_for(self, article_id: str) -> Path:
        # File names may contain colons; keep them verbatim
        return self.directory / f"{article_id}.json"

    def get(self, article_id: str) -> dict | None:
        return self._load_all().get(article_id)

    def list_all(self) -> list[dict]:
        return list(self._load_all().values())


store = ArticleStore(KNOWLEDGE_DIR)


def _load_sources() -> list[dict]:
    """Load RSS sources from config with defaults."""
    if not RSS_CONFIG.exists():
        return []
    config = yaml.safe_load(RSS_CONFIG.read_text(encoding="utf-8")) or {}
    sources = []
    for src in config.get("sources", []):
        sources.append({
            "slug": src.get("slug"),
            "name": src.get("name"),
            "url": src.get("url"),
            "category": src.get("category", "general"),
            "per_source_limit": src.get("per_source_limit", 5),
            "enabled": src.get("enabled", True),
        })
    return sources


def _last_7d_count_by_source(articles_dir: Path) -> dict[str, int]:
    """Count articles from last 7 days by source slug."""
    counts: dict[str, int] = {}
    if not articles_dir.exists():
        return counts
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for path in articles_dir.glob("*.json"):
        if path.name in ("index.json", "_skipped.jsonl"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            collected_at_str = data.get("collected_at")
            if not collected_at_str:
                continue
            collected_at = datetime.fromisoformat(collected_at_str)
            if collected_at >= cutoff:
                # source is like "rss:Source Name", try to match back to slug
                # fallback: use slug if id starts with slug
                source = data.get("source", "")
                # For now, let's just use the filename prefix as the slug
                filename = path.stem
                # filename is like "slug-YYYYMMDD-NNN"
                if "-" in filename:
                    slug_candidate = filename.split("-", 1)[0]
                    counts[slug_candidate] = counts.get(slug_candidate, 0) + 1
        except Exception:  # noqa: BLE001
            continue
    return counts


def _atomic_write_yaml(config: dict, path: Path) -> None:
    """Write YAML config atomically using tmp file then replace."""
    tmp_path = path.with_suffix(".yaml.tmp")
    tmp_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp_path, path)


def _normalize_article(data: dict) -> dict:
    """Ensure consistent field presence with defaults."""
    defaults = {
        "id": "",
        "title": "",
        "source": "",
        "source_url": "",
        "url": "",
        "author": "",
        "published_at": "",
        "collected_at": "",
        "summary": "",
        "tags": [],
        "status": "draft",
        "score": 5,
        "audience": "intermediate",
        "relevance_score": 0.0,
        "category": "",
        "key_insight": "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    merged = {**defaults, **data}
    # Ensure tags is a list
    if not isinstance(merged.get("tags"), list):
        merged["tags"] = []
    # Normalize category into list for easier UI consumption
    merged["categories"] = _split_category(merged.get("category", ""))
    return merged


def _split_category(category_str: str | None) -> list[str]:
    if not category_str:
        return []
    return [c.strip() for c in str(category_str).split("|") if c.strip()]


def _join_category(categories: list[str]) -> str:
    return "|".join(categories)


# ─── API Endpoints ──────────────────────────────────────────────────────────


@app.route("/api/articles", methods=["GET"])
def list_articles():
    articles = store.list_all()
    normalized = [_normalize_article(a) for a in articles]

    # Filters
    source = request.args.get("source", "").strip()
    tag = request.args.get("tag", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    audience = request.args.get("audience", "").strip()
    q = request.args.get("q", "").strip().lower()

    if source:
        normalized = [a for a in normalized if a.get("source") == source]
    if tag:
        normalized = [a for a in normalized if tag in (a.get("tags") or [])]
    if category:
        normalized = [a for a in normalized if category in a.get("categories", [])]
    if status:
        normalized = [a for a in normalized if a.get("status") == status]
    if audience:
        normalized = [a for a in normalized if a.get("audience") == audience]
    if q:
        normalized = [
            a
            for a in normalized
            if q in a.get("title", "").lower() or q in a.get("summary", "").lower()
        ]

    # Date range filter (on updated_at)
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    if from_date:
        normalized = [a for a in normalized if a.get("updated_at", "") >= from_date]
    if to_date:
        # Extend to end of day
        to_iso = to_date + "T23:59:59"
        normalized = [a for a in normalized if a.get("updated_at", "") <= to_iso]

    # Sort
    sort = request.args.get("sort", "updated_at")
    if sort == "updated_at":
        normalized.sort(key=lambda a: a.get("updated_at", ""), reverse=True)
    elif sort == "published_at":
        normalized.sort(key=lambda a: a.get("published_at", ""), reverse=True)
    elif sort == "score":
        normalized.sort(key=lambda a: a.get("score", 0), reverse=True)
    elif sort == "title":
        normalized.sort(key=lambda a: a.get("title", "").lower())

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    limit = max(1, min(100, request.args.get("limit", 20, type=int)))
    total = len(normalized)
    start = (page - 1) * limit
    end = start + limit
    items = normalized[start:end]

    return jsonify(
        {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        }
    )


@app.route("/api/articles/<article_id>", methods=["GET"])
def get_article(article_id: str):
    article = store.get(article_id)
    if not article:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_normalize_article(article))


@app.route("/api/articles/<article_id>", methods=["PATCH"])
def patch_article(article_id: str):
    article = store.get(article_id)
    if not article:
        return jsonify({"error": "Not found"}), 404

    payload = request.get_json(silent=True) or {}
    allowed_fields = {
        "title",
        "summary",
        "tags",
        "status",
        "score",
        "audience",
        "category",
        "key_insight",
        "author",
    }

    for key, value in payload.items():
        if key in allowed_fields:
            article[key] = value

    article["updated_at"] = datetime.now(timezone.utc).isoformat()
    store._write(article_id, article)
    return jsonify(_normalize_article(article))


@app.route("/api/articles/<article_id>", methods=["DELETE"])
def delete_article(article_id: str):
    article = store.get(article_id)
    if not article:
        return jsonify({"error": "Not found"}), 404
    store._delete(article_id)
    return jsonify({"success": True})


@app.route("/api/articles/batch", methods=["POST"])
def batch_operation():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    action = payload.get("action", "")
    params = payload.get("params", {})

    if not ids or action not in {"archive", "delete", "tag", "untag", "category", "status"}:
        return jsonify({"error": "Invalid batch request"}), 400

    updated = []
    for aid in ids:
        article = store.get(aid)
        if not article:
            continue
        if action == "archive":
            article["status"] = "archived"
            article["updated_at"] = datetime.now(timezone.utc).isoformat()
            store._write(aid, article)
            updated.append(aid)
        elif action == "delete":
            store._delete(aid)
            updated.append(aid)
        elif action == "tag":
            new_tags = params.get("tags", [])
            if new_tags:
                article["tags"] = list(set(article.get("tags", []) + new_tags))
                article["updated_at"] = datetime.now(timezone.utc).isoformat()
                store._write(aid, article)
                updated.append(aid)
        elif action == "category":
            new_cat = params.get("category", "")
            if new_cat:
                article["category"] = new_cat
                article["updated_at"] = datetime.now(timezone.utc).isoformat()
                store._write(aid, article)
                updated.append(aid)
        elif action == "status":
            new_status = params.get("status", "")
            if new_status:
                article["status"] = new_status
                article["updated_at"] = datetime.now(timezone.utc).isoformat()
                store._write(aid, article)
                updated.append(aid)
        elif action == "untag":
            remove_tags = params.get("tags", [])
            if remove_tags:
                article["tags"] = [t for t in article.get("tags", []) if t not in remove_tags]
                article["updated_at"] = datetime.now(timezone.utc).isoformat()
                store._write(aid, article)
                updated.append(aid)

    return jsonify({"success": True, "updated": updated})


@app.route("/api/articles/export", methods=["POST"])
def export_articles():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    if not ids:
        return jsonify({"error": "No ids provided"}), 400
    articles = []
    for aid in ids:
        article = store.get(aid)
        if article:
            articles.append(article)
    return jsonify({"articles": articles, "count": len(articles)})


@app.route("/api/articles/import", methods=["POST"])
def import_articles():
    payload = request.get_json(silent=True) or {}
    articles = payload.get("articles", [])
    if not articles:
        return jsonify({"error": "No articles provided"}), 400
    imported = 0
    skipped = 0
    for article in articles:
        aid = article.get("id")
        if not aid:
            skipped += 1
            continue
        article["updated_at"] = datetime.now(timezone.utc).isoformat()
        store._write(aid, article)
        imported += 1
    return jsonify({"success": True, "imported": imported, "skipped": skipped})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    articles = store.list_all()
    normalized = [_normalize_article(a) for a in articles]
    total = len(normalized)

    sources: dict[str, int] = {}
    tags: dict[str, int] = {}
    categories: dict[str, int] = {}
    statuses: dict[str, int] = {}

    for a in normalized:
        src = a.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        for t in a.get("tags", []):
            tags[t] = tags.get(t, 0) + 1
        for c in a.get("categories", []):
            categories[c] = categories.get(c, 0) + 1
        st = a.get("status", "unknown")
        statuses[st] = statuses.get(st, 0) + 1

    return jsonify(
        {
            "total": total,
            "sources": sources,
            "tags": tags,
            "categories": categories,
            "statuses": statuses,
        }
    )


@app.route("/api/filters", methods=["GET"])
def get_filters():
    articles = store.list_all()
    normalized = [_normalize_article(a) for a in articles]

    sources = sorted({a.get("source", "") for a in normalized if a.get("source")})
    tags = sorted({t for a in normalized for t in a.get("tags", [])})
    categories = sorted({c for a in normalized for c in a.get("categories", [])})
    statuses = sorted({a.get("status", "") for a in normalized if a.get("status")})
    audiences = sorted({a.get("audience", "") for a in normalized if a.get("audience")})

    return jsonify(
        {
            "sources": sources,
            "tags": tags,
            "categories": categories,
            "statuses": statuses,
            "audiences": audiences,
        }
    )


@app.route("/api/sources", methods=["GET"])
def list_sources():
    sources = _load_sources()
    counts = _last_7d_count_by_source(KNOWLEDGE_DIR)
    for src in sources:
        src["last_7d_count"] = counts.get(src["slug"], 0)
    return jsonify(sources)


@app.route("/api/sources/<slug>", methods=["PATCH"])
def patch_source(slug: str):
    if not RSS_CONFIG.exists():
        return jsonify({"error": "RSS config not found"}), 404
    payload = request.get_json(silent=True) or {}
    if "enabled" not in payload or not isinstance(payload["enabled"], bool):
        return jsonify({"error": "Invalid body: 'enabled' boolean required"}), 400
    config = yaml.safe_load(RSS_CONFIG.read_text(encoding="utf-8")) or {}
    sources = config.get("sources", [])
    found = False
    for src in sources:
        if src.get("slug") == slug:
            src["enabled"] = payload["enabled"]
            found = True
            break
    if not found:
        return jsonify({"error": "Source not found"}), 404
    _atomic_write_yaml(config, RSS_CONFIG)
    # Return updated sources list
    updated_sources = _load_sources()
    counts = _last_7d_count_by_source(KNOWLEDGE_DIR)
    for src in updated_sources:
        src["last_7d_count"] = counts.get(src["slug"], 0)
    return jsonify(updated_sources)


# ─── SPA static serving ─────────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def index():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
