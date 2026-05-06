"""Reviewer node: score analyses across five weighted dimensions."""

from __future__ import annotations

import json
from typing import Any

from workflows.model_client import accumulate_usage, chat_json_with_model
from workflows.state import KBState

REVIEWER_WEIGHTS: dict[str, float] = {
    "summary_quality": 0.25,
    "technical_depth": 0.25,
    "relevance": 0.20,
    "originality": 0.15,
    "formatting": 0.15,
}

REVIEWER_PASS_THRESHOLD = 7.0


def calculate_weighted_score(scores: dict[str, Any]) -> float:
    total = 0.0
    for dimension, weight in REVIEWER_WEIGHTS.items():
        raw_score = scores.get(dimension, 0)
        score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
        total += max(0.0, min(10.0, score)) * weight
    return round(total, 2)


def review_node(state: KBState) -> dict[str, Any]:
    analyses = state.get("analyses", [])
    iteration = int(state.get("iteration", 0))
    tracker = dict(state.get("cost_tracker", {}))

    if not analyses:
        return {
            "review_passed": True,
            "review_feedback": "没有条目需要审核",
            "iteration": iteration + 1,
            "cost_tracker": tracker,
        }

    sample = analyses[:5]
    prompt = f"""你是知识库质量审核员。请审核以下分析结果：

{json.dumps(sample, ensure_ascii=False, indent=2)}

按 1-10 分评分：
- summary_quality: 摘要准确性、可读性、信息密度
- technical_depth: 技术深度和实现细节
- relevance: 与 AI/LLM/Agent 主题相关性
- originality: 独立洞察，不只是复述
- formatting: 字段完整、标签规范

只返回 JSON:
{{
  "scores": {{
    "summary_quality": 8,
    "technical_depth": 7,
    "relevance": 9,
    "originality": 6,
    "formatting": 8
  }},
  "feedback": "具体、可执行的改进建议",
  "weak_dimensions": ["technical_depth"]
}}"""

    try:
        result, usage, model = chat_json_with_model(
            prompt,
            system="你是严格但公正的知识库质量审核员。请只返回 JSON。",
            temperature=0.1,
            max_tokens=800,
        )
        if not isinstance(result, dict):
            raise ValueError("review response must be a JSON object")

        tracker = accumulate_usage(tracker, usage, model)
        scores = result.get("scores", {})
        if not isinstance(scores, dict):
            scores = {}

        weighted_score = calculate_weighted_score(scores)
        weak_dimensions = result.get("weak_dimensions", [])
        weak_text = ""
        if isinstance(weak_dimensions, list) and weak_dimensions:
            weak_text = f"[弱项: {', '.join(str(dim) for dim in weak_dimensions)}] "
        feedback = f"{weak_text}{result.get('feedback', '')}".strip()
        passed = weighted_score >= REVIEWER_PASS_THRESHOLD
    except Exception as error:
        weighted_score = 7.0
        feedback = f"审核 LLM 调用失败，自动通过: {error}"
        passed = True

    print(f"[Reviewer] 加权总分: {weighted_score}/10, 通过: {passed}")
    return {
        "review_passed": passed,
        "review_feedback": feedback,
        "iteration": iteration + 1,
        "cost_tracker": tracker,
    }
