"""Shared state contract for the LangGraph knowledge workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypedDict


SourceName = Literal["github", "rss"]


class Plan(TypedDict):
    strategy: Literal["full", "standard", "lite"]
    per_source_limit: int
    relevance_threshold: float
    max_iterations: int
    rationale: str


class CostTracker(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float


class KBState(TypedDict, total=False):
    """Global LangGraph state.

    Each node returns only the keys it owns. LangGraph merges those partial
    updates into this shared state.
    """

    plan: Plan
    requested_sources: list[SourceName]
    dry_run: bool
    sources: list[dict[str, Any]]
    analyses: list[dict[str, Any]]
    articles: list[dict[str, Any]]
    review_feedback: str
    review_passed: bool
    iteration: int
    needs_human_review: bool
    cost_tracker: CostTracker
    articles_dir: Path
    pending_review_dir: Path
