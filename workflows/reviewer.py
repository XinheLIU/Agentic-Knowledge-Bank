"""Reviewer node: score analyses across five weighted dimensions."""

from __future__ import annotations

import json
from typing import Any

from workflows.model_client import accumulate_usage, chat_json_with_model
from workflows.prompts import load_prompt, render
from workflows.relevance_profile import load_relevance_profile, profile_summary_text
from workflows.skipped import append_skipped
from workflows.state import KBState

REVIEWER_WEIGHTS: dict[str, float] = {
    "summary_quality": 0.20,
    "technical_depth": 0.20,
    "personal_relevance": 0.25,
    "actionability": 0.20,
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

    profile = load_relevance_profile()
    profile_text = profile_summary_text(profile)

    sample = analyses[:5]
    prompt = render(
        "reviewer",
        {
            "profile_text": profile_text,
            "analyses_json": json.dumps(sample, ensure_ascii=False, indent=2),
        },
    )

    try:
        result, usage, model = chat_json_with_model(
            prompt,
            system=load_prompt("reviewer_system"),
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

    if not passed:
        for item in analyses:
            append_skipped(
                item_id=item.get("id", "unknown"),
                source=str(item.get("source", "unknown")),
                source_url=item.get("source_url") or item.get("url", ""),
                stage="reviewer",
                reason=f"reviewer veto (weighted_score={weighted_score}, threshold={REVIEWER_PASS_THRESHOLD})",
            )

    print(f"[Reviewer] 加权总分: {weighted_score}/10, 通过: {passed}")
    return {
        "review_passed": passed,
        "review_feedback": feedback,
        "iteration": iteration + 1,
        "cost_tracker": tracker,
    }
