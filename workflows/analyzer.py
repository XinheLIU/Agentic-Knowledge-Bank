"""Analyzer node: enrich raw items one at a time with LLM output."""

from __future__ import annotations

from typing import Any

from workflows.model_client import Usage, accumulate_usage, chat_json_with_model
from workflows.prompts import render
from workflows.relevance_profile import (
    VALID_LEARNING_TRACKS,
    VALID_READING_PRIORITIES,
    VALID_SOURCE_TYPES,
    VALID_SUGGESTED_ACTIONS,
    load_relevance_profile,
    profile_summary_text,
)
from workflows.skipped import append_skipped
from workflows.state import KBState

VALID_BROAD_TAGS = {
    "agent", "rag", "mcp", "llm", "fine-tuning", "prompt-engineering",
    "multi-agent", "tool-use", "evaluation", "deployment", "security",
    "reasoning", "code-generation", "vision", "audio", "robotics",
}

VALID_LEARNING_TAGS = {
    "agent-harness", "langgraph", "langchain", "data-agent", "mcp",
    "tool-use", "browser-agent", "computer-use", "evaluation",
    "repo-tutorial", "reference-architecture", "paper-to-code",
    "production-rag", "local-llm", "quant-ai", "business-context",
    "implementation-pattern", "architecture-reference", "production-lesson",
    "research-method", "noise",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return ["llm"]

    normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    valid = [tag for tag in normalized if tag in VALID_BROAD_TAGS]
    return valid[:3] or ["llm"]


def _normalize_learning_tags(tags: Any, allowlist: set[str] | None = None) -> list[str]:
    if not isinstance(tags, list):
        return []

    allowed = allowlist or VALID_LEARNING_TAGS
    normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    return [tag for tag in normalized if tag in allowed]


def _normalize_reading_priority(value: Any) -> str:
    val = str(value).strip().lower() if value else ""
    return val if val in VALID_READING_PRIORITIES else "low-priority"


def _normalize_source_type(value: Any) -> str:
    val = str(value).strip().lower() if value else ""
    return val if val in VALID_SOURCE_TYPES else "unknown"


def _normalize_learning_track(value: Any) -> str:
    val = str(value).strip().lower() if value else ""
    return val if val in VALID_LEARNING_TRACKS else "background"


def _normalize_suggested_action(value: Any) -> str:
    val = str(value).strip().lower() if value else ""
    return val if val in VALID_SUGGESTED_ACTIONS else "skim"


def _apply_rule_caps(
    reading_priority: str,
    source_type: str,
    personal_fit: float,
    focus_topics_match: bool,
) -> str:
    if source_type in ("discussion", "news") and personal_fit < 0.5:
        return min_priority(reading_priority, "low-priority")

    if source_type in ("discussion", "news") and personal_fit < 0.7:
        return min_priority(reading_priority, "skim")

    if focus_topics_match and personal_fit >= 0.6:
        return max_priority(reading_priority, "save-for-context")

    return reading_priority


PRIORITY_ORDER = ["skip", "low-priority", "skim", "save-for-context", "study-now"]


def max_priority(a: str, b: str) -> str:
    ia = PRIORITY_ORDER.index(a) if a in PRIORITY_ORDER else 1
    ib = PRIORITY_ORDER.index(b) if b in PRIORITY_ORDER else 1
    return PRIORITY_ORDER[max(ia, ib)]


def min_priority(a: str, b: str) -> str:
    ia = PRIORITY_ORDER.index(a) if a in PRIORITY_ORDER else 1
    ib = PRIORITY_ORDER.index(b) if b in PRIORITY_ORDER else 1
    return PRIORITY_ORDER[min(ia, ib)]


def _check_focus_match(item_title: str, item_desc: str, profile: dict[str, Any]) -> bool:
    text = f"{item_title} {item_desc}".lower()
    p0 = profile.get("focus_topics", {}).get("p0_must_learn", [])
    return any(topic.lower() in text for topic in p0)


def _fallback_analysis(item: dict[str, Any], error: Exception) -> dict[str, Any]:
    description = item.get("raw_description", "") or item.get("description", "")
    summary = description.strip()[:240] or f"{item.get('title', '未知条目')} 暂未获得可用摘要，LLM 分析失败: {error}"
    if len(summary) < 20:
        summary = f"{summary}。该条目保留为低分草稿，等待后续人工或模型复核。"

    return {
        **item,
        "summary": summary,
        "tags": ["llm"],
        "relevance_score": 0.0,
        "category": item.get("category", "error"),
        "key_insight": "",
        "score": 1,
        "audience": "intermediate",
        "status": "draft",
        "personal_fit_score": 0.0,
        "technical_depth_score": 0.0,
        "actionability_score": 0.0,
        "source_credibility_score": 0.0,
        "novelty_score": 0.0,
        "priority_score": 0,
        "reading_priority": "low-priority",
        "relevance_reason": f"LLM 分析失败: {error}",
        "suggested_action": "skim",
        "confidence": 0.0,
        "source_type": "unknown",
        "learning_track": "background",
        "learning_tags": [],
    }


def analyze_item(item: dict[str, Any], profile: dict[str, Any] | None = None) -> tuple[dict[str, Any], Usage, str]:
    active_profile = profile or load_relevance_profile()
    profile_text = profile_summary_text(active_profile)
    learning_tag_list = active_profile.get("learning_tag_allowlist", list(VALID_LEARNING_TAGS))

    prompt = render(
        "analyzer",
        {
            "profile_text": profile_text,
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "url": item.get("source_url", item.get("url", "")),
            "description": item.get("raw_description", item.get("description", "")),
            "learning_tags": ", ".join(learning_tag_list),
        },
    )

    result, usage, model = chat_json_with_model(prompt, temperature=0.3, max_tokens=900)
    if not isinstance(result, dict):
        raise ValueError("LLM analysis response must be a JSON object")

    personal_fit = _clamp(float(result.get("personal_fit_score", 0.5)), 0.0, 1.0)
    tech_depth = _clamp(float(result.get("technical_depth_score", 0.5)), 0.0, 1.0)
    actionability = _clamp(float(result.get("actionability_score", 0.5)), 0.0, 1.0)
    source_cred = _clamp(float(result.get("source_credibility_score", 0.5)), 0.0, 1.0)
    novelty = _clamp(float(result.get("novelty_score", 0.5)), 0.0, 1.0)

    priority_score = max(0, min(100, int(result.get("priority_score", 50))))

    source_type = _normalize_source_type(result.get("source_type"))
    learning_track = _normalize_learning_track(result.get("learning_track"))

    reading_priority = _normalize_reading_priority(result.get("reading_priority"))

    item_text = f"{item.get('title', '')} {item.get('raw_description', item.get('description', ''))}"
    focus_match = _check_focus_match(item.get("title", ""), item.get("raw_description", item.get("description", "")), active_profile)
    reading_priority = _apply_rule_caps(reading_priority, source_type, personal_fit, focus_match)

    relevance_score = personal_fit

    score = max(1, min(10, round(priority_score / 10))) if priority_score > 0 else max(1, min(10, int(result.get("score", 5))))

    enriched = {
        **item,
        "summary": str(result.get("summary", "")).strip(),
        "tags": _normalize_tags(result.get("tags", [])),
        "relevance_score": relevance_score,
        "category": str(result.get("category", "other")).strip() or "other",
        "key_insight": str(result.get("key_insight", "")).strip(),
        "score": score,
        "audience": result.get("audience", "intermediate")
        if result.get("audience") in {"beginner", "intermediate", "advanced"}
        else "intermediate",
        "status": "review",
        "personal_fit_score": personal_fit,
        "technical_depth_score": tech_depth,
        "actionability_score": actionability,
        "source_credibility_score": source_cred,
        "novelty_score": novelty,
        "priority_score": priority_score,
        "reading_priority": reading_priority,
        "relevance_reason": str(result.get("relevance_reason", "")).strip(),
        "suggested_action": _normalize_suggested_action(result.get("suggested_action")),
        "confidence": _clamp(float(result.get("confidence", 0.5)), 0.0, 1.0),
        "source_type": source_type,
        "learning_track": learning_track,
        "learning_tags": _normalize_learning_tags(result.get("learning_tags"), set(learning_tag_list)),
    }
    return enriched, usage, model


def analyze_node(state: KBState) -> dict[str, Any]:
    analyses: list[dict[str, Any]] = []
    tracker = dict(state.get("cost_tracker", {}))
    plan = state.get("plan", {})
    relevance_threshold = float(plan.get("relevance_threshold", 0.5))

    profile = load_relevance_profile()

    for item in state.get("sources", []):
        try:
            analysis, usage, model = analyze_item(item, profile=profile)
            tracker = accumulate_usage(tracker, usage, model)
        except Exception as error:
            print(f"[Analyzer] 分析失败: {item.get('title', '?')} - {error}")
            analysis = _fallback_analysis(item, error)

        if float(analysis.get("relevance_score", 0.0)) < relevance_threshold:
            item_id = analysis.get("id", "unknown")
            append_skipped(
                item_id=item_id,
                source=str(analysis.get("source", "unknown")),
                source_url=analysis.get("source_url") or analysis.get("url", ""),
                stage="analyzer",
                reason=f"relevance_score {analysis.get('relevance_score')} < threshold {relevance_threshold}",
            )
            print(f"[Analyzer] 淘汰 (低分): {item.get('title', '?')} score={analysis.get('relevance_score')}")
            continue

        analyses.append(analysis)

    print(f"[Analyzer] 完成 {len(analyses)} 条分析")
    return {"analyses": analyses, "cost_tracker": tracker}
