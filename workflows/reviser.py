"""Reviser node: update analyses using reviewer feedback."""

from __future__ import annotations

import json
from typing import Any

from workflows.model_client import accumulate_usage, chat_json_with_model
from workflows.state import KBState


def revise_node(state: KBState) -> dict[str, Any]:
    analyses = state.get("analyses", [])
    feedback = state.get("review_feedback", "")
    tracker = dict(state.get("cost_tracker", {}))

    if not analyses or not feedback:
        return {"cost_tracker": tracker}

    prompt = f"""请根据审核反馈定向修改分析结果，只返回修改后的 JSON 数组。

审核反馈:
{feedback}

当前分析结果:
{json.dumps(analyses, ensure_ascii=False, indent=2)}

要求:
- 保持数组长度和字段结构。
- 优先改进反馈指出的弱项。
- 不要删除 source_url、id、title、source、collected_at 等溯源字段。"""

    try:
        result, usage, model = chat_json_with_model(
            prompt,
            system="你是知识库编辑。根据反馈定向修改，不要过度扩写。请只返回 JSON。",
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
