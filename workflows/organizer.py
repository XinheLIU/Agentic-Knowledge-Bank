"""Organizer node: normalize approved analyses and persist articles."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflows.skipped import append_skipped
from workflows.state import KBState

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"

CATEGORIES = {"llm", "agent", "rag", "mcp", "evaluation", "deployment", "security", "other"}


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _slug_source(source: str) -> str:
    slug = re.sub(r"[^a-z0-9:-]+", "-", source.lower()).strip("-")
    return slug or "unknown"


def _existing_urls(articles_dir: Path) -> set[str]:
    urls: set[str] = set()
    if not articles_dir.exists():
        return urls

    for path in articles_dir.glob("*.json"):
        if path.name in ("index.json", "_skipped.jsonl"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        source_url = data.get("source_url")
        if isinstance(source_url, str) and source_url:
            urls.add(source_url)
    return urls


def _normalize_category(item: dict[str, Any]) -> dict[str, Any]:
    """Ensure category is a single valid value.

    Multi-value strings are downgraded: first part becomes category,
    rest are appended to tags, and status is set to review.
    """
    cat = item.get("category", "other")
    if not isinstance(cat, str):
        cat = str(cat) if cat is not None else "other"

    cat = cat.strip()

    if "|" in cat:
        parts = [p.strip() for p in cat.split("|") if p.strip()]
        item["category"] = parts[0] if parts else "other"
        for p in parts[1:]:
            tag = p.lower()
            if tag not in item.get("tags", []):
                item.setdefault("tags", []).append(tag)
        item["status"] = "review"
        return item

    if cat not in CATEGORIES:
        item["category"] = "other"
        item["status"] = "review"
    else:
        item["category"] = cat

    return item


def _validate_article(item: dict[str, Any]) -> list[str]:
    """Lightweight schema validation before persistence."""
    errors: list[str] = []
    required = ["id", "title", "source_url", "summary", "tags", "status",
                "key_insight", "category", "relevance_score", "url"]
    for field in required:
        if field not in item or item[field] in ("", None):
            errors.append(f"missing {field}")
    return errors


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

        article = {
            "id": article_id,
            "title": item.get("title", ""),
            "source": source,
            "source_url": source_url,
            "url": item.get("url") or source_url,
            "author": item.get("author") if item.get("author") is not None else None,
            "published_at": item.get("published_at") if item.get("published_at") is not None else None,
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
            "personal_fit_score": _clamp_float(item.get("personal_fit_score"), 0.0, 1.0, 0.0),
            "technical_depth_score": _clamp_float(item.get("technical_depth_score"), 0.0, 1.0, 0.0),
            "actionability_score": _clamp_float(item.get("actionability_score"), 0.0, 1.0, 0.0),
            "source_credibility_score": _clamp_float(item.get("source_credibility_score"), 0.0, 1.0, 0.0),
            "novelty_score": _clamp_float(item.get("novelty_score"), 0.0, 1.0, 0.0),
            "priority_score": max(0, min(100, int(item.get("priority_score", 0)))),
            "reading_priority": item.get("reading_priority", "low-priority")
            if item.get("reading_priority") in {"study-now", "save-for-context", "skim", "low-priority", "skip"}
            else "low-priority",
            "relevance_reason": str(item.get("relevance_reason", "")).strip(),
            "suggested_action": item.get("suggested_action", "skim")
            if item.get("suggested_action") in {"clone-and-study", "deep-read", "skim", "archive", "skip"}
            else "skim",
            "confidence": _clamp_float(item.get("confidence"), 0.0, 1.0, 0.5),
            "source_type": item.get("source_type", "unknown")
            if item.get("source_type") in {"repository", "paper", "blog", "discussion", "benchmark", "tutorial", "product", "news", "documentation", "unknown"}
            else "unknown",
            "learning_track": item.get("learning_track", "background")
            if item.get("learning_track") in {"agent-systems", "langgraph-workflows", "data-agents", "rag-knowledge-systems", "evaluation", "local-model-serving", "ml-rl-foundations", "quant-data-science", "engineering-leadership", "business-context", "background"}
            else "background",
            "learning_tags": item.get("learning_tags") if isinstance(item.get("learning_tags"), list) else [],
        }

        article = _normalize_category(article)

        validation_errors = _validate_article(article)
        if validation_errors:
            append_skipped(
                item_id=article_id,
                source=source,
                source_url=source_url,
                stage="organizer",
                reason=f"schema validation failed: {', '.join(validation_errors)}",
            )
            continue

        articles.append(article)

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

    return saved_paths


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
