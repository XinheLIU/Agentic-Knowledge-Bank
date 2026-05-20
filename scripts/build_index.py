#!/usr/bin/env python3
"""Rebuild knowledge/articles/index.json from all article JSON files.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --articles-dir knowledge/articles
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ARTICLES_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "articles"

EXCLUDED_NAMES = {"index.json", "_skipped.jsonl"}


def build_index(articles_dir: Path) -> list[dict[str, Any]]:
    """Scan articles_dir and return a fresh index list."""
    index: list[dict[str, Any]] = []

    if not articles_dir.exists():
        return index

    for path in sorted(articles_dir.glob("*.json")):
        if path.name in EXCLUDED_NAMES:
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        index.append({
            "id": data.get("id"),
            "title": data.get("title"),
            "source": data.get("source"),
            "source_url": data.get("source_url"),
            "category": data.get("category", "other"),
            "relevance_score": data.get("relevance_score", 0.5),
        })

    return index


def save_index(index: list[dict[str, Any]], articles_dir: Path) -> Path:
    """Write index.json to articles_dir."""
    articles_dir.mkdir(parents=True, exist_ok=True)
    index_path = articles_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild knowledge index")
    parser.add_argument("--articles-dir", type=Path, default=DEFAULT_ARTICLES_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Print count but do not write")
    args = parser.parse_args()

    index = build_index(args.articles_dir)
    print(f"[build_index] 扫描到 {len(index)} 条文章")

    if not args.dry_run:
        path = save_index(index, args.articles_dir)
        print(f"[build_index] 已写入 {path}")
    else:
        print("[build_index] dry-run，未写入")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
