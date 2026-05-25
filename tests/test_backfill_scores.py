from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts.backfill_scores import (
    article_to_raw_item,
    discover_article_paths,
    merge_backfilled_article,
)

pytestmark = pytest.mark.non_llm


def test_article_to_raw_item_uses_summary_as_raw_description():
    article = {
        "id": "rss:test-20260524-001",
        "title": "Test Article",
        "source": "rss:Test",
        "source_url": "https://example.com/source",
        "url": "https://example.com/source",
        "author": "author",
        "published_at": "2026-05-24T00:00:00+00:00",
        "collected_at": "2026-05-24T01:00:00+00:00",
        "summary": "Existing summary becomes analyzer input.",
    }

    raw_item = article_to_raw_item(article)

    assert raw_item["id"] == "rss:test-20260524-001"
    assert raw_item["title"] == "Test Article"
    assert raw_item["source"] == "rss:Test"
    assert raw_item["source_url"] == "https://example.com/source"
    assert raw_item["raw_description"] == "Existing summary becomes analyzer input."
    assert raw_item["description"] == "Existing summary becomes analyzer input."


def test_merge_backfilled_article_preserves_identity_and_status():
    original = {
        "id": "rss:test-20260524-001",
        "title": "Old Title",
        "source": "rss:Test",
        "source_url": "https://example.com/source",
        "url": "https://example.com/source",
        "author": "original author",
        "published_at": "2026-05-24T00:00:00+00:00",
        "collected_at": "2026-05-24T01:00:00+00:00",
        "summary": "Old summary",
        "status": "published",
    }
    enriched = {
        "id": "new-id",
        "title": "New Title",
        "source": "different-source",
        "source_url": "https://example.com/different",
        "url": "https://example.com/different",
        "author": "different author",
        "published_at": "2026-05-25T00:00:00+00:00",
        "collected_at": "2026-05-25T01:00:00+00:00",
        "summary": "New summary",
        "status": "review",
        "personal_fit_score": 0.9,
        "reading_priority": "study-now",
    }

    merged = merge_backfilled_article(original, enriched)

    assert merged["id"] == "rss:test-20260524-001"
    assert merged["source"] == "rss:Test"
    assert merged["source_url"] == "https://example.com/source"
    assert merged["url"] == "https://example.com/source"
    assert merged["author"] == "original author"
    assert merged["published_at"] == "2026-05-24T00:00:00+00:00"
    assert merged["collected_at"] == "2026-05-24T01:00:00+00:00"
    assert merged["summary"] == "New summary"
    assert merged["status"] == "published"
    assert merged["personal_fit_score"] == 0.9
    assert merged["reading_priority"] == "study-now"


def test_discover_article_paths_prefers_filename_date_over_mtime(tmp_path):
    recent_by_name = tmp_path / "rss:test-20260524-001.json"
    old_by_name = tmp_path / "rss:test-20260521-001.json"

    for path in [recent_by_name, old_by_name]:
        path.write_text(json.dumps({"id": path.stem}), encoding="utf-8")

    now = datetime(2026, 5, 25, tzinfo=timezone.utc)

    import os

    fresh_mtime = now.timestamp() - 12 * 60 * 60
    old_mtime = now.timestamp() - 10 * 24 * 60 * 60
    os.utime(recent_by_name, (old_mtime, old_mtime))
    os.utime(old_by_name, (fresh_mtime, fresh_mtime))

    paths = discover_article_paths(tmp_path, days=3, now=now)

    assert paths == [recent_by_name]


def test_discover_article_paths_filters_by_mtime(tmp_path):
    recent = tmp_path / "recent.json"
    old = tmp_path / "old.json"
    index = tmp_path / "index.json"

    for path in [recent, old, index]:
        path.write_text(json.dumps({"id": path.stem}), encoding="utf-8")

    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    recent_mtime = now.timestamp() - 12 * 60 * 60
    old_mtime = now.timestamp() - 4 * 24 * 60 * 60
    index_mtime = recent_mtime

    recent.touch()
    old.touch()
    index.touch()
    recent.chmod(0o644)
    old.chmod(0o644)
    index.chmod(0o644)

    import os

    os.utime(recent, (recent_mtime, recent_mtime))
    os.utime(old, (old_mtime, old_mtime))
    os.utime(index, (index_mtime, index_mtime))

    paths = discover_article_paths(tmp_path, days=3, now=now)

    assert paths == [recent]
