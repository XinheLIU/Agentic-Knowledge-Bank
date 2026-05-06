"""Collector node: gather raw items from GitHub and RSS."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import httpx
import yaml

from workflows.state import KBState, SourceName

logger = logging.getLogger(__name__)
RSS_CONFIG = Path(__file__).with_name("rss_sources.yaml")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_github(limit: int = 10) -> list[dict[str, Any]]:
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
    for index, repo in enumerate(data.get("items", [])[:limit], 1):
        items.append({
            "id": f"github-{date_key}-{index:03d}",
            "title": repo.get("full_name", ""),
            "source": "github",
            "source_url": repo.get("html_url", ""),
            "url": repo.get("html_url", ""),
            "author": repo.get("owner", {}).get("login", "unknown"),
            "published_at": repo.get("pushed_at", ""),
            "raw_description": repo.get("description", "") or "",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "language": repo.get("language", ""),
            "topics": repo.get("topics", []),
            "category": "open-source",
            "collected_at": collected_at,
        })
    return items


def collect_rss(limit: int = 10, config_path: Path = RSS_CONFIG) -> list[dict[str, Any]]:
    if not config_path.exists():
        logger.warning("RSS config missing: %s", config_path)
        return []

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sources = [source for source in config.get("sources", []) if source.get("enabled", True)]
    items: list[dict[str, Any]] = []

    with httpx.Client(timeout=20.0) as client:
        for source in sources:
            if len(items) >= limit:
                break

            try:
                response = client.get(source["url"])
                response.raise_for_status()
                feed = feedparser.parse(response.text)
            except httpx.HTTPError as error:
                logger.warning("RSS source failed [%s]: %s", source.get("name", "?"), error)
                continue

            for entry in feed.entries:
                if len(items) >= limit:
                    break

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                index = len(items) + 1
                collected_at = _utc_now()
                date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
                items.append({
                    "id": f"rss-{date_key}-{index:03d}",
                    "title": title,
                    "source": f"rss:{source['name']}",
                    "source_url": link,
                    "url": link,
                    "author": source.get("name", "unknown"),
                    "published_at": collected_at,
                    "raw_description": entry.get("summary", ""),
                    "category": source.get("category", "general"),
                    "collected_at": collected_at,
                })

    return items


def collect_node(state: KBState) -> dict[str, list[dict[str, Any]]]:
    plan = state.get("plan", {})
    limit = int(plan.get("per_source_limit", 10))
    requested_sources: list[SourceName] = state.get("requested_sources", ["github", "rss"])

    items: list[dict[str, Any]] = []
    if "github" in requested_sources:
        items.extend(collect_github(limit))
    if "rss" in requested_sources:
        items.extend(collect_rss(limit))

    print(f"[Collector] 采集到 {len(items)} 条原始数据")
    return {"sources": items}
