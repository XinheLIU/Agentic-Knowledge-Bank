"""Collector node: gather raw items from GitHub and RSS."""

from __future__ import annotations

import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
import yaml

from workflows.skipped import read_skipped_ids
from workflows.state import KBState, SourceName

logger = logging.getLogger(__name__)
RSS_CONFIG = Path(__file__).with_name("rss_sources.yaml")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"
DEFAULT_PER_SOURCE_LIMIT = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_feed_pubdate(entry: Any) -> str | None:
    """Parse RSS/Atom entry publication date into ISO 8601 string.

    Prefers ``published_parsed``, falls back to ``updated_parsed``.
    Returns ``None`` when no parseable date is present.
    """
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            return None
    return None


def _used_indices(slug: str, date_key: str, articles_dir: Path) -> set[int]:
    """Scan articles_dir and _skipped.jsonl for used NNN indices."""
    used: set[int] = set()
    prefix = f"{slug}-{date_key}-"

    if articles_dir.exists():
        for path in articles_dir.glob("*.json"):
            if path.name in ("index.json", "_skipped.jsonl"):
                continue
            name = path.stem
            if name.startswith(prefix) and len(name) == len(prefix) + 3:
                try:
                    used.add(int(name[-3:]))
                except ValueError:
                    continue

    skipped_ids = read_skipped_ids(articles_dir / "_skipped.jsonl")
    for item_id in skipped_ids:
        if item_id.startswith(prefix) and len(item_id) == len(prefix) + 3:
            try:
                used.add(int(item_id[-3:]))
            except ValueError:
                continue

    return used


def _allocate_id(slug: str, date_key: str, articles_dir: Path) -> str:
    """Allocate next available id for (slug, date_key)."""
    used = _used_indices(slug, date_key, articles_dir)
    for nnn in range(1, 1000):
        if nnn not in used:
            return f"{slug}-{date_key}-{nnn:03d}"
    raise RuntimeError(f"Ran out of indices for {slug}-{date_key}")


def collect_github(limit: int = 10, articles_dir: Path = ARTICLES_DIR) -> list[dict[str, Any]]:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {
        "q": f"ai agent llm stars:>100 pushed:>{one_week_ago}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }

    items: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as error:
        logger.warning("GitHub collection failed: %s", error)
        return []

    collected_at = _utc_now()
    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    for _index, repo in enumerate(data.get("items", [])[:limit], 1):
        article_id = _allocate_id("github", date_key, articles_dir)
        items.append({
            "id": article_id,
            "title": repo.get("full_name", ""),
            "source": "github",
            "source_url": repo.get("html_url", ""),
            "url": repo.get("html_url", ""),
            "author": repo.get("owner", {}).get("login") or None,
            "published_at": repo.get("pushed_at") or None,
            "raw_description": repo.get("description", "") or "",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "language": repo.get("language", ""),
            "topics": repo.get("topics", []),
            "category": "open-source",
            "collected_at": collected_at,
        })
    return items


def _fingerprint(title: str, url: str) -> str:
    """Compute a normalized fingerprint from title and URL domain."""
    norm_title = re.sub(r"[^\w\u4e00-\u9fff]+", "", title.lower())
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return f"{domain}|{norm_title}"


def _existing_fingerprints(articles_dir: Path) -> set[str]:
    """Reconstruct existing fingerprints from articles_dir."""
    fingerprints: set[str] = set()
    if not articles_dir.exists():
        return fingerprints
    for path in articles_dir.glob("*.json"):
        if path.name in ("index.json", "_skipped.jsonl"):
            continue
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            if "title" in data and "source_url" in data:
                fp = _fingerprint(data["title"], data["source_url"])
                fingerprints.add(fp)
        except Exception:  # noqa: BLE001
            continue
    return fingerprints


def collect_rss(
    limit: int = 10,
    config_path: Path = RSS_CONFIG,
    articles_dir: Path = ARTICLES_DIR,
) -> list[dict[str, Any]]:
    if not config_path.exists():
        logger.warning("RSS config missing: %s", config_path)
        return []

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sources = [source for source in config.get("sources", []) if source.get("enabled", True)]
    
    # Validate all sources have slugs first
    for source in sources:
        slug = source.get("slug")
        if not slug:
            raise ValueError(f"RSS source '{source.get('name', '?')}' missing required 'slug' field")

    # Compute per-source quotas with proportional scaling
    total_requested = sum(src.get("per_source_limit", DEFAULT_PER_SOURCE_LIMIT) for src in sources)
    actual_quotas: dict[str, int] = {}
    if total_requested <= limit:
        for src in sources:
            actual_quotas[src["slug"]] = src.get("per_source_limit", DEFAULT_PER_SOURCE_LIMIT)
    else:
        scale = limit / total_requested
        for src in sources:
            base = src.get("per_source_limit", DEFAULT_PER_SOURCE_LIMIT)
            actual_quotas[src["slug"]] = max(1, math.ceil(base * scale))

    items: list[dict[str, Any]] = []
    existing_fps = _existing_fingerprints(articles_dir)
    seen_fps: set[str] = set()

    for source in sources:
        slug = source["slug"]  # Already validated
        quota = actual_quotas.get(slug, DEFAULT_PER_SOURCE_LIMIT)
        collected_from_source = 0

        try:
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                response = client.get(source["url"])
                response.raise_for_status()
                feed = feedparser.parse(response.text)
        except httpx.HTTPError as error:
            logger.warning("RSS source failed [%s]: %s", source.get("name", "?"), error)
            continue

        for entry in feed.entries:
            if collected_from_source >= quota:
                break

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            fp = _fingerprint(title, link)
            if fp in existing_fps or fp in seen_fps:
                continue

            collected_at = _utc_now()
            date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
            article_id = _allocate_id(slug, date_key, articles_dir)
            items.append({
                "id": article_id,
                "title": title,
                "source": f"rss:{source['name']}",
                "source_url": link,
                "url": link,
                "author": entry.get("author") or None,
                "published_at": _parse_feed_pubdate(entry),
                "raw_description": entry.get("summary", ""),
                "category": source.get("category", "general"),
                "collected_at": collected_at,
            })
            seen_fps.add(fp)
            collected_from_source += 1

    # Enforce hard global limit (in case ceil made it over)
    return items[:limit]


def collect_node(state: KBState) -> dict[str, list[dict[str, Any]]]:
    plan = state.get("plan", {})
    limit = int(plan.get("per_source_limit", 10))
    requested_sources: list[SourceName] = state.get("requested_sources", ["github", "rss"])
    articles_dir = Path(state.get("articles_dir") or ARTICLES_DIR)

    items: list[dict[str, Any]] = []
    if "github" in requested_sources:
        items.extend(collect_github(limit, articles_dir=articles_dir))
    if "rss" in requested_sources:
        items.extend(collect_rss(limit, articles_dir=articles_dir))

    print(f"[Collector] 采集到 {len(items)} 条原始数据")
    return {"sources": items}
