"""
RSS source collection module.

Configured sources live in pipeline/rss_sources.yaml.

Usage:
    # Imported by pipeline.py.
    from pipeline.rss_reader import collect_rss
    items = collect_rss(limit=10)

    # Standalone debugging.
    python3 -m pipeline.rss_reader
    python3 -m pipeline.rss_reader --limit 5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import httpx
import yaml

logger = logging.getLogger(__name__)

# Shared with pipeline.py.
RSS_CONFIG = Path(__file__).parent / "rss_sources.yaml"


def collect_rss(limit: int = 10) -> list[dict[str, Any]]:
    """
    Collect entries from configured RSS sources.

    Args:
        limit: Maximum number of entries across all sources.

    Returns:
        Raw records with id/title/source/source_url fields.
    """
    if not RSS_CONFIG.exists():
        logger.warning("RSS 配置文件不存在: %s", RSS_CONFIG)
        return []

    with open(RSS_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = [s for s in config.get("sources", []) if s.get("enabled", True)]
    results: list[dict[str, Any]] = []
    count = 0

    with httpx.Client(timeout=20.0) as client:
        for source in sources:
            if count >= limit:
                break

            try:
                resp = client.get(source["url"])
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    if count >= limit:
                        break

                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    if not title or not link:
                        continue

                    count += 1
                    now = datetime.now(timezone.utc).isoformat()
                    results.append({
                        "id": f"rss-{datetime.now().strftime('%Y%m%d')}-{count:03d}",
                        "title": title,
                        "source": f"rss:{source['name']}",
                        "source_url": link,
                        "author": source.get("name", "unknown"),
                        "published_at": now,
                        "raw_description": entry.get("summary", ""),
                        "category": source.get("category", "general"),
                        "collected_at": now,
                    })

                logger.info("RSS [%s] 采集: %d 条", source["name"], len(feed.entries))

            except httpx.HTTPError as e:
                logger.warning("RSS 源 [%s] 获取失败: %s", source["name"], e)

    logger.info("RSS 采集完成: 共 %d 条", len(results))
    return results


if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="RSS 数据源采集调试入口")
    parser.add_argument("--limit", type=int, default=10, help="最大采集条数")
    parser.add_argument("--output", type=str, default="", help="保存到 JSON 文件（可选）")
    args = parser.parse_args()

    items = collect_rss(limit=args.limit)
    print(f"\n采集到 {len(items)} 条 RSS 条目")
    for i, item in enumerate(items[:5], 1):
        print(f"  {i}. [{item['source']}] {item['title'][:60]}")
    if len(items) > 5:
        print(f"  ... 还有 {len(items) - 5} 条")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到: {args.output}")
