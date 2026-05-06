"""Analyzer node: enrich raw items one at a time with LLM output."""

from __future__ import annotations

from typing import Any

from workflows.model_client import Usage, accumulate_usage, chat_json_with_model
from workflows.state import KBState

VALID_TAGS = {
    "agent", "rag", "mcp", "llm", "fine-tuning", "prompt-engineering",
    "multi-agent", "tool-use", "evaluation", "deployment", "security",
    "reasoning", "code-generation", "vision", "audio", "robotics",
}


def _normalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return ["llm"]

    normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    valid = [tag for tag in normalized if tag in VALID_TAGS]
    return valid[:3] or ["llm"]


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
    }


def analyze_item(item: dict[str, Any]) -> tuple[dict[str, Any], Usage, str]:
    prompt = f"""请分析以下 AI 技术内容，只返回 JSON。

标题: {item.get('title', '')}
来源: {item.get('source', '')}
URL: {item.get('source_url', item.get('url', ''))}
描述: {item.get('raw_description', item.get('description', ''))}

JSON 格式:
{{
  "summary": "50-160字中文技术摘要，说明核心价值",
  "tags": ["llm", "agent"],
  "relevance_score": 0.8,
  "category": "llm|agent|rag|mcp|evaluation|deployment|security|other",
  "key_insight": "一句话洞察",
  "score": 7,
  "audience": "beginner|intermediate|advanced"
}}"""

    result, usage, model = chat_json_with_model(prompt, temperature=0.3, max_tokens=700)
    if not isinstance(result, dict):
        raise ValueError("LLM analysis response must be a JSON object")

    enriched = {
        **item,
        "summary": str(result.get("summary", "")).strip(),
        "tags": _normalize_tags(result.get("tags", [])),
        "relevance_score": float(result.get("relevance_score", 0.5)),
        "category": str(result.get("category", "other")).strip() or "other",
        "key_insight": str(result.get("key_insight", "")).strip(),
        "score": max(1, min(10, int(result.get("score", 5)))),
        "audience": result.get("audience", "intermediate")
        if result.get("audience") in {"beginner", "intermediate", "advanced"}
        else "intermediate",
        "status": "review",
    }
    return enriched, usage, model


def analyze_node(state: KBState) -> dict[str, Any]:
    analyses: list[dict[str, Any]] = []
    tracker = dict(state.get("cost_tracker", {}))

    for item in state.get("sources", []):
        try:
            analysis, usage, model = analyze_item(item)
            tracker = accumulate_usage(tracker, usage, model)
            analyses.append(analysis)
        except Exception as error:
            print(f"[Analyzer] 分析失败: {item.get('title', '?')} - {error}")
            analyses.append(_fallback_analysis(item, error))

    print(f"[Analyzer] 完成 {len(analyses)} 条分析")
    return {"analyses": analyses, "cost_tracker": tracker}
