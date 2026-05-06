"""LangGraph topology and CLI for AI-KB v0.5.0."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from workflows.analyzer import analyze_node
from workflows.collector import collect_node
from workflows.human_flag import human_flag_node
from workflows.organizer import organize_node
from workflows.planner import planner_node
from workflows.reviewer import review_node
from workflows.reviser import revise_node
from workflows.state import KBState, SourceName


def route_after_review(state: KBState) -> str:
    plan = state.get("plan", {})
    max_iterations = int(plan.get("max_iterations", 3))
    iteration = int(state.get("iteration", 0))

    if state.get("review_passed", False):
        return "organize"
    if iteration >= max_iterations:
        return "human_flag"
    return "revise"


def build_graph() -> StateGraph:
    graph = StateGraph(KBState)
    graph.add_node("plan", planner_node)
    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("review", review_node)
    graph.add_node("revise", revise_node)
    graph.add_node("organize", organize_node)
    graph.add_node("human_flag", human_flag_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "review")
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "organize": "organize",
            "revise": "revise",
            "human_flag": "human_flag",
        },
    )
    graph.add_edge("revise", "review")
    graph.add_edge("organize", END)
    graph.add_edge("human_flag", END)
    return graph


def initial_state(
    sources: list[SourceName],
    limit: int,
    dry_run: bool,
    articles_dir: Path | None = None,
    pending_review_dir: Path | None = None,
) -> KBState:
    return {
        "requested_sources": sources,
        "dry_run": dry_run,
        "plan": {
            "strategy": "standard",
            "per_source_limit": limit,
            "relevance_threshold": 0.5,
            "max_iterations": 2,
            "rationale": "CLI provided initial limit; planner may normalize strategy.",
        },
        "sources": [],
        "analyses": [],
        "articles": [],
        "review_feedback": "",
        "review_passed": False,
        "iteration": 0,
        "needs_human_review": False,
        "cost_tracker": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost_usd": 0.0,
        },
        "articles_dir": articles_dir,
        "pending_review_dir": pending_review_dir,
    }


def parse_sources(raw_sources: str) -> list[SourceName]:
    allowed = {"github", "rss"}
    sources = [source.strip().lower() for source in raw_sources.split(",") if source.strip()]
    invalid = [source for source in sources if source not in allowed]
    if invalid:
        raise ValueError(f"Unsupported sources: {', '.join(invalid)}")
    return sources or ["github", "rss"]


def run_workflow(
    sources: list[SourceName],
    limit: int = 20,
    dry_run: bool = False,
    articles_dir: Path | None = None,
    pending_review_dir: Path | None = None,
) -> dict[str, Any]:
    app = build_graph().compile()
    final_state = app.invoke(
        initial_state(
            sources=sources,
            limit=limit,
            dry_run=dry_run,
            articles_dir=articles_dir,
            pending_review_dir=pending_review_dir,
        )
    )
    return {
        "collected": len(final_state.get("sources", [])),
        "analyzed": len(final_state.get("analyses", [])),
        "published": len(final_state.get("articles", [])),
        "needs_human_review": final_state.get("needs_human_review", False),
        "cost_tracker": final_state.get("cost_tracker", {}),
        "dry_run": dry_run,
    }


def enforce_run_policies(
    stats: dict[str, Any],
    *,
    fail_on_human_flag: bool = False,
    min_published: int = 0,
) -> None:
    if fail_on_human_flag and stats.get("needs_human_review", False):
        raise SystemExit("Workflow entered human_flag terminal state")

    if stats.get("published", 0) < min_published:
        raise SystemExit(
            f"Workflow published {stats.get('published', 0)} articles, "
            f"below required minimum {min_published}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-KB LangGraph workflow")
    parser.add_argument("--sources", default="github,rss", help="Comma-separated: github,rss")
    parser.add_argument("--limit", type=int, default=20, help="Per-source collection limit")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing articles")
    parser.add_argument("--provider", default=None, help="Override LLM_PROVIDER")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--fail-on-human-flag",
        action="store_true",
        help="Exit non-zero if the workflow ends in human_flag",
    )
    parser.add_argument(
        "--min-published",
        type=int,
        default=0,
        help="Exit non-zero if fewer than this many articles are published",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final workflow stats as JSON",
    )
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    stats = run_workflow(
        sources=parse_sources(args.sources),
        limit=args.limit,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        print(
            "[Workflow] 完成: "
            f"采集={stats['collected']} 分析={stats['analyzed']} "
            f"发布={stats['published']} 人工介入={stats['needs_human_review']}"
        )

    enforce_run_policies(
        stats,
        fail_on_human_flag=args.fail_on_human_flag,
        min_published=args.min_published,
    )


if __name__ == "__main__":
    main()
