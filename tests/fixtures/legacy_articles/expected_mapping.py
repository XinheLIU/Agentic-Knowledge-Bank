"""Deterministic mapping + search reference for ticket 04 (revised after verification).

Two layers, deliberately separated:

1. ``map_legacy_article()`` / ``legacy_search_rank()`` — an *implementation-like* pure
   reference of the behavior the future legacy import adapter (ticket 07/08) must
   reproduce. It derives outputs from inputs.

2. ``expected_mapped.jsonl`` / ``expected_search.json`` — the *static immutable
   oracle*: hand-pinned expected results for every fixture article, committed as data.
   Tests must compare layer 1 against layer 2; layer 1 changing without the oracle
   changing is a migration-behavior regression.

Canonical identity follows ticket 02 / ADR 0001: the legacy import adapter mints
``legacy:<opaque legacy id>`` exactly once (e.g. ``legacy:rss:mitchell-hashimoto-20260530-010``);
the raw legacy id is never treated as already-canonical, and no stage re-derives it.
"""

from __future__ import annotations

import re
from typing import Any

# Canonical ID rule for the new asset store (ticket 02 / ADR 0001): colon-legal,
# minted once as <radar>:<opaque id>; legacy imports mint "legacy:" + legacy id.
CANONICAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9:._-]*$")

# Legacy validator rule (hooks/validate_json.py) — kept here only to reproduce G1.
LEGACY_ID_PATTERN = re.compile(r"^[a-z0-9-]+-\d{8}-\d{3}$")

# v0.6+ personalization fields with no canonical column (R-D7 drop list).
DROPPED_FIELDS = frozenset(
    {
        "personal_fit_score",
        "technical_depth_score",
        "actionability_score",
        "source_credibility_score",
        "novelty_score",
        "priority_score",
        "reading_priority",
        "relevance_reason",
        "suggested_action",
        "confidence",
        "learning_track",
        "learning_tags",
        "relevance_score",
        "score",
    }
)

LEGACY_ID_PREFIX = "legacy:"


def mint_canonical_id(legacy_id: str) -> str:
    """Mint the canonical asset id from a legacy id, exactly once.

    Per ADR 0001 the import adapter mints ``legacy:<opaque legacy id>`` once; the
    legacy id is opaque and never re-derived or re-slugged.
    """
    legacy_id = str(legacy_id)
    if not CANONICAL_ID_PATTERN.match(legacy_id):
        raise ValueError(f"legacy id not mintable: {legacy_id!r}")
    return LEGACY_ID_PREFIX + legacy_id


def canonical_id(legacy_id: str) -> str:
    """Back-compat alias for mint_canonical_id."""
    return mint_canonical_id(legacy_id)


def map_legacy_article(article: dict[str, Any]) -> dict[str, Any]:
    """Map one legacy article record to the canonical asset row shape.

    Deterministic and side-effect free. The result contains exactly the canonical
    columns relevant at baseline (no personalization fields, no fabricated defaults).
    """
    source_url = article.get("source_url") or article.get("url") or ""
    if not source_url:
        raise ValueError(f"record {article.get('id')!r} has no URL")

    content_main = article.get("description")
    if content_main is None:
        content_main = article.get("raw_description")

    legacy_id = str(article["id"])
    return {
        "id": mint_canonical_id(legacy_id),
        "legacy_id": legacy_id,
        "title": str(article["title"]),
        "url": str(source_url),
        "author": article.get("author"),  # may be None → SQL NULL
        "source_type": article.get("source_type"),  # may be None → SQL NULL
        "published_at": article.get("published_at"),
        "summary": str(article["summary"]),
        "content_main": content_main,  # None when the record carries no body text
        "legacy_id_has_colon": ":" in legacy_id,
        "legacy_id_valid_under_old_rule": bool(LEGACY_ID_PATTERN.match(legacy_id)),
        "dropped_fields": sorted(DROPPED_FIELDS & set(article.keys())),
    }


def legacy_search_rank(keyword: str, article: dict[str, Any]) -> float:
    """Reproduce mcp_knowledge_server.search_articles ranking (without I/O)."""
    kw = keyword.lower()
    title = str(article.get("title", "")).lower()
    summary = str(article.get("summary", "")).lower()
    if kw not in title and kw not in summary:
        return float("-inf")
    score = 0.0
    if kw in title:
        score += 10
    if kw in summary:
        score += 3
    score += float(article.get("relevance_score") or 0) * 2
    return score


def implementation_search_hits(
    keyword: str, articles: list[dict[str, Any]], limit: int = 5
) -> list[str]:
    """Implementation-like search: rank legacy records, return minted canonical ids.

    Mirrors the legacy MCP ranking so ticket 11/12 consumers can compare against the
    pre-cutover behavior; ranks are deterministic because fixture ids/urls are unique.
    """
    ranked = sorted(
        ((legacy_search_rank(keyword, a), str(a["id"])) for a in articles),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [mint_canonical_id(aid) for rank, aid in ranked if rank != float("-inf")][:limit]
