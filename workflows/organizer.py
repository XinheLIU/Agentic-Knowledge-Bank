"""Organizer node: normalize approved analyses and persist articles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflows.state import KBState

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"


def _slug_source(source: str) -> str:
    slug = re.sub(r"[^a-z0-9:-]+", "-", source.lower()).strip("-")
    return slug or "unknown"


def _existing_urls(articles_dir: Path) -> set[str]:
    urls: set[str] = set()
    if not articles_dir.exists():
        return urls

    for path in articles_dir.glob("*.json"):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        source_url = data.get("source_url")
        if isinstance(source_url, str) and source_url:
            urls.add(source_url)
    return urls


def build_articles(
    analyses: list[dict[str, Any]],
    relevance_threshold: float,
    articles_dir: Path = ARTICLES_DIR,
) -> list[dict[str, Any]]:
    seen_urls = _existing_urls(articles_dir)
    articles: list[dict[str, Any]] = []
    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    now = datetime.now(timezone.utc).isoformat()

    for item in analyses:
        if float(item.get("relevance_score", 0.0)) < relevance_threshold:
            continue

        source_url = item.get("source_url") or item.get("url", "")
        if not source_url or source_url in seen_urls:
            continue

        seen_urls.add(source_url)
        source = str(item.get("source", "unknown"))
        article_index = len(articles) + 1
        article_id = f"{_slug_source(source)}-{date_key}-{article_index:03d}"
        summary = str(item.get("summary", "")).strip()
        if len(summary) < 20:
            summary = f"{summary}。该条目摘要不足，需后续复核补充技术细节。"

        articles.append({
            "id": article_id,
            "title": item.get("title", ""),
            "source": source,
            "source_url": source_url,
            "url": source_url,
            "author": item.get("author", "unknown"),
            "published_at": item.get("published_at", ""),
            "collected_at": item.get("collected_at", now),
            "summary": summary,
            "tags": item.get("tags") or ["llm"],
            "status": "published",
            "score": max(1, min(10, int(item.get("score", 5)))),
            "audience": item.get("audience", "intermediate")
            if item.get("audience") in {"beginner", "intermediate", "advanced"}
            else "intermediate",
            "relevance_score": float(item.get("relevance_score", 0.5)),
            "category": item.get("category", "other"),
            "key_insight": item.get("key_insight", ""),
            "updated_at": now,
        })

    return articles


def save_articles(articles: list[dict[str, Any]], articles_dir: Path = ARTICLES_DIR) -> list[Path]:
    if not articles:
        return []

    articles_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for article in articles:
        path = articles_dir / f"{article['id']}.json"
        path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        saved_paths.append(path)

    update_index(articles, articles_dir)
    return saved_paths


def update_index(articles: list[dict[str, Any]], articles_dir: Path = ARTICLES_DIR) -> None:
    index_path = articles_dir / "index.json"
    index: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                index = existing
        except json.JSONDecodeError:
            index = []

    existing_ids = {entry.get("id") for entry in index if isinstance(entry, dict)}
    for article in articles:
        if article["id"] in existing_ids:
            continue
        index.append({
            "id": article["id"],
            "title": article["title"],
            "source": article["source"],
            "source_url": article["source_url"],
            "category": article.get("category", "other"),
            "relevance_score": article.get("relevance_score", 0.5),
        })

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def organize_node(state: KBState) -> dict[str, Any]:
    plan = state.get("plan", {})
    articles_dir = Path(state.get("articles_dir") or ARTICLES_DIR)
    articles = build_articles(
        analyses=state.get("analyses", []),
        relevance_threshold=float(plan.get("relevance_threshold", 0.6)),
        articles_dir=articles_dir,
    )

    if not state.get("dry_run", False):
        saved_paths = save_articles(articles, articles_dir=articles_dir)
    else:
        saved_paths = [articles_dir / f"{article['id']}.json" for article in articles]

    print(f"[Organizer] 整理 {len(articles)} 条，写入 {len(saved_paths)} 个文件")
    return {"articles": articles, "cost_tracker": state.get("cost_tracker", {})}
