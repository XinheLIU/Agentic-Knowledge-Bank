#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_index import build_index, save_index  # noqa: E402
from workflows.analyzer import analyze_item  # noqa: E402
from workflows.relevance_profile import load_relevance_profile  # noqa: E402

ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"
EXCLUDED_NAMES = {"index.json", "_skipped.jsonl"}
IDENTITY_FIELDS = ["id", "collected_at", "published_at", "author", "source_url", "url", "source"]
ARTICLE_DATE_PATTERN = re.compile(r"-(\d{8})-\d{3}\.json$")


@dataclass(frozen=True)
class BackfillStats:
    selected: int = 0
    backfilled: int = 0
    skipped: int = 0
    errors: int = 0

    def with_selected(self, selected: int) -> "BackfillStats":
        return BackfillStats(selected=selected, backfilled=self.backfilled, skipped=self.skipped, errors=self.errors)

    def record_backfilled(self) -> "BackfillStats":
        return BackfillStats(selected=self.selected, backfilled=self.backfilled + 1, skipped=self.skipped, errors=self.errors)

    def record_skipped(self) -> "BackfillStats":
        return BackfillStats(selected=self.selected, backfilled=self.backfilled, skipped=self.skipped + 1, errors=self.errors)

    def record_error(self) -> "BackfillStats":
        return BackfillStats(selected=self.selected, backfilled=self.backfilled, skipped=self.skipped, errors=self.errors + 1)


def _article_date_from_name(path: Path) -> datetime | None:
    match = ARTICLE_DATE_PATTERN.search(path.name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_recent_article_path(path: Path, cutoff_timestamp: float, cutoff_date: datetime) -> bool:
    article_date = _article_date_from_name(path)
    if article_date is not None:
        return article_date >= cutoff_date

    try:
        return path.stat().st_mtime >= cutoff_timestamp
    except OSError:
        return False


def discover_article_paths(articles_dir: Path, days: int, now: datetime | None = None) -> list[Path]:
    active_now = now or datetime.now(timezone.utc)
    cutoff_timestamp = active_now.timestamp() - days * 24 * 60 * 60
    cutoff_date = datetime.fromtimestamp(cutoff_timestamp, tz=timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if not articles_dir.exists():
        return []

    paths: list[Path] = []
    for path in sorted(articles_dir.glob("*.json")):
        if path.name in EXCLUDED_NAMES:
            continue
        if _is_recent_article_path(path, cutoff_timestamp, cutoff_date):
            paths.append(path)
    return paths


def article_to_raw_item(article: dict[str, Any]) -> dict[str, Any]:
    source_url = str(article.get("source_url") or article.get("url") or "")
    return {
        "id": article.get("id", ""),
        "title": article.get("title", ""),
        "source": article.get("source", "unknown"),
        "source_url": source_url,
        "url": article.get("url") or source_url,
        "author": article.get("author") if article.get("author") is not None else None,
        "published_at": article.get("published_at") if article.get("published_at") is not None else None,
        "collected_at": article.get("collected_at"),
        "raw_description": article.get("summary", ""),
        "description": article.get("summary", ""),
    }


def merge_backfilled_article(original: dict[str, Any], enriched: dict[str, Any]) -> dict[str, Any]:
    merged = dict(original)
    merged.update(enriched)

    for field in IDENTITY_FIELDS:
        if field in original:
            merged[field] = original[field]

    merged["status"] = "published"
    return merged


def load_article(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("article JSON must be an object")
    return data


def save_article(path: Path, article: dict[str, Any]) -> None:
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")


def backfill_article(path: Path, profile: dict[str, Any], dry_run: bool) -> tuple[bool, str | None]:
    try:
        original = load_article(path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return False, f"read failed: {error}"

    if dry_run:
        return True, None

    try:
        enriched, _, _ = analyze_item(article_to_raw_item(original), profile=profile)
    except Exception as error:
        return False, f"LLM analysis failed: {error}"

    updated = merge_backfilled_article(original, enriched)

    try:
        save_article(path, updated)
    except OSError as error:
        return False, f"write failed: {error}"

    return True, None


def run_backfill(articles_dir: Path, days: int, dry_run: bool) -> BackfillStats:
    profile = load_relevance_profile()
    paths = discover_article_paths(articles_dir, days)
    stats = BackfillStats().with_selected(len(paths))

    print(f"[backfill_scores] selected={len(paths)} days={days} dry_run={dry_run}")

    for path in paths:
        ok, error = backfill_article(path, profile, dry_run=dry_run)
        if ok:
            stats = stats.record_skipped() if dry_run else stats.record_backfilled()
            print(f"[backfill_scores] {'would backfill' if dry_run else 'backfilled'} {path.name}")
            continue

        stats = stats.record_error()
        print(f"[backfill_scores] skipped {path.name}: {error}")

    if not dry_run:
        index = build_index(articles_dir)
        index_path = save_index(index, articles_dir)
        print(f"[backfill_scores] rebuilt {index_path} ({len(index)} articles)")

    print(
        "[backfill_scores] done "
        f"selected={stats.selected} backfilled={stats.backfilled} "
        f"skipped={stats.skipped} errors={stats.errors}"
    )
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill v0.6.0 scoring fields for existing articles")
    parser.add_argument("--days", type=int, default=3, help="Select articles modified within this many days")
    parser.add_argument("--dry-run", action="store_true", help="List target articles without LLM calls or writes")
    parser.add_argument("--provider", default=None, help="Override LLM_PROVIDER")
    parser.add_argument("--articles-dir", type=Path, default=ARTICLES_DIR, help="Article directory")
    parser.add_argument("--debug", action="store_true", help="Print traceback on failure")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.days < 1:
        raise SystemExit("--days must be >= 1")
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    try:
        stats = run_backfill(args.articles_dir, args.days, args.dry_run)
    except Exception:
        if args.debug:
            traceback.print_exc()
        raise

    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
