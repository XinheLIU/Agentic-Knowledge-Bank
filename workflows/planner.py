"""Planner node: choose workflow strategy before execution."""

from __future__ import annotations

import os

from workflows.state import KBState, Plan


def plan_strategy(target_count: int | None = None) -> Plan:
    """Choose the smallest strategy that satisfies the target collection size."""
    if target_count is None:
        target_count = int(os.getenv("PLANNER_TARGET_COUNT", "10"))

    if target_count >= 20:
        return {
            "strategy": "full",
            "per_source_limit": 20,
            "relevance_threshold": 0.4,
            "max_iterations": 3,
            "rationale": f"目标 {target_count} 条，启用深度模式（质量优先）",
        }
    elif target_count >= 10:
        return {
            "strategy": "standard",
            "per_source_limit": 10,
            "relevance_threshold": 0.5,
            "max_iterations": 2,
            "rationale": f"目标 {target_count} 条，启用标准模式（平衡模式）",
        }
    else:
        return {
            "strategy": "lite",
            "per_source_limit": 5,
            "relevance_threshold": 0.7,
            "max_iterations": 1,
            "rationale": f"目标 {target_count} 条，启用精简模式（成本优先）",
        }


def planner_node(state: KBState) -> dict:
    """Write the selected execution plan into graph state."""
    requested_sources = state.get("requested_sources", ["github", "rss"])
    target_count = int(os.getenv("PLANNER_TARGET_COUNT", "10"))
    if state.get("plan"):
        target_count = int(state["plan"].get("per_source_limit", target_count))

    plan = plan_strategy(target_count)
    plan["per_source_limit"] = max(1, plan["per_source_limit"])
    print(
        f"[Planner] 策略={plan['strategy']}, 每源={plan['per_source_limit']} 条, "
        f"数据源={','.join(requested_sources)}, 阈值={plan['relevance_threshold']}"
    )
    return {"plan": plan}


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("Planner 模式演示 — 3 种目标采集量的策略输出")
    print("=" * 60)
    for tc in [5, 15, 30]:
        print(f"\n【target_count={tc}】")
        print(json.dumps(plan_strategy(tc), ensure_ascii=False, indent=2))
