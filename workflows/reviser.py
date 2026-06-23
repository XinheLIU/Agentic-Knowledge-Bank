"""Reviser node: update analyses using reviewer feedback."""

from __future__ import annotations

import json
from typing import Any

from workflows.model_client import accumulate_usage, chat_json_with_model
from workflows.prompts import load_prompt, render
from workflows.state import KBState


def revise_node(state: KBState) -> dict[str, Any]:
    analyses = state.get("analyses", [])
    feedback = state.get("review_feedback", "")
    tracker = dict(state.get("cost_tracker", {}))

    if not analyses or not feedback:
        return {"cost_tracker": tracker}

    prompt = render(
        "reviser",
        {
            "feedback": feedback,
            "analyses_json": json.dumps(analyses, ensure_ascii=False, indent=2),
        },
    )

    try:
        result, usage, model = chat_json_with_model(
            prompt,
            system=load_prompt("reviser_system"),
            temperature=0.4,
            max_tokens=2000,
        )
        tracker = accumulate_usage(tracker, usage, model)
        if isinstance(result, list) and result:
            print(f"[Reviser] 定向修改 {len(result)} 条分析")
            return {"analyses": result, "cost_tracker": tracker}
    except Exception as error:
        print(f"[Reviser] 修改失败，沿用原分析: {error}")

    return {"cost_tracker": tracker}
