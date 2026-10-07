"""Fixtures for the store test suite: representative Horizon-mapped rows.

Rows follow the ticket-01 contract shapes exercised by
``tests/test_kb_operator_surface.py`` after ``map_item``; the store must accept
them without Horizon transport involvement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kb.horizon.contract import map_item


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def horizon_item(
    item_id: str = "github:acme:widget#1",
    *,
    title: str = "A Horizon item",
    url: str | None = None,
    score: float = 8.0,
    summary: str = "有用的摘要 with mechanism",
    tags: list[str] | None = None,
    source_type: str = "github",
    published_at: str = "2026-09-11T08:00:00+00:00",
    **extra: Any,
) -> dict[str, Any]:
    """A ContentItem-shaped dict (verified ticket-01 contract)."""
    return {
        "id": item_id,
        "source_type": source_type,
        "title": title,
        "url": url or f"https://example.com/{item_id.replace('#', '_')}",
        "author": None,
        "published_at": published_at,
        "fetched_at": "2026-09-11T09:00:00+00:00",
        "content": "main body content",
        "metadata": {"upstream": "kept-bounded"},
        "profile": ["tech-news"],
        "processing": {
            "classification": {
                "profile": "tech-news",
                "method": "ai_match",
                "confidence": 0.9,
                "reason": "matches P0 topics",
            },
            "analysis": {
                "score": score,
                "reason": "directly relevant",
                "summary": summary,
                "tags": tags if tags is not None else ["mcp", "tool-use"],
            },
            "artifacts": {
                "zh": {
                    "title": "中文标题",
                    "blocks": [
                        {"id": "b1", "type": "summary", "title": "摘要",
                         "content": "中文内容", "source_refs": ["s1"], "primary": True},
                        {"id": "b2", "type": "takeaway", "title": "要点",
                         "content": "中文要点", "source_refs": [], "primary": False},
                    ],
                    "sources": [
                        {"id": "s1", "title": "upstream", "url": "https://example.com/src"},
                    ],
                },
                "en": {
                    "title": "English title",
                    "blocks": [
                        {"id": "b1", "type": "summary", "title": "Summary",
                         "content": "English content", "source_refs": [], "primary": True},
                    ],
                    "sources": [],
                },
            },
        },
        **extra,
    }


def mapped_store_item(raw: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """``map_item`` output shaped for ``items`` (write-once asset row)."""
    mapped = map_item(raw or horizon_item(**kwargs))
    mapped["fetched_at"] = mapped.get("fetched_at") or _now()
    return mapped
