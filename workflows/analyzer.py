"""Analyzer node: enrich raw items one at a time with LLM output."""

from __future__ import annotations

from typing import Any

from workflows.model_client import Usage, accumulate_usage, chat_json_with_model
from workflows.skipped import append_skipped
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
  "category": "从下列单一值中选一个：llm、agent、rag、mcp、evaluation、deployment、security、other",
  "key_insight": "一句话洞察",
  "score": 7,
  "audience": "beginner|intermediate|advanced"
}}

重要约束：
- category 必须是单个字符串，不要返回 "agent|evaluation" 这种多值字符串，也不要返回数组。
- audience 判断请先输出理由，再给出取值。示例：
  1. 这是一篇介绍 Transformer 基础原理的科普文章，面向刚接触 NLP 的读者 → beginner
  2. 本文深入讨论多智能体协作中的共识机制与消息路由，需要读者具备 LLM 应用开发经验 → intermediate
  3. 论文提出了新的注意力复杂度下界证明，并给出了形式化推导，面向领域研究者 → advanced
"""

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
    plan = state.get("plan", {})
    relevance_threshold = float(plan.get("relevance_threshold", 0.5))

    for item in state.get("sources", []):
        try:
            analysis, usage, model = analyze_item(item)
            tracker = accumulate_usage(tracker, usage, model)
        except Exception as error:
            print(f"[Analyzer] 分析失败: {item.get('title', '?')} - {error}")
            analysis = _fallback_analysis(item, error)

        # Write full relevance_score regardless of threshold (D7)
        # If below threshold, record to skipped log and drop from pipeline
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
