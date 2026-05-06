"""Tests for the LangGraph workflow topology and organizer behavior."""

from __future__ import annotations

import json

import pytest

from workflows.graph import (
    enforce_run_policies,
    initial_state,
    parse_sources,
    route_after_review,
)
from workflows.human_flag import write_pending_review
from workflows.human_flag import human_flag_node
from workflows.organizer import build_articles, save_articles
from workflows.organizer import organize_node
from workflows.planner import plan_strategy
from workflows.reviewer import calculate_weighted_score

pytestmark = pytest.mark.non_llm


def test_plan_strategy_thresholds():
    assert plan_strategy(5)["strategy"] == "lite"
    assert plan_strategy(10)["strategy"] == "standard"
    assert plan_strategy(20)["strategy"] == "full"


def test_route_after_review_passes_to_organizer():
    state = initial_state(["github"], limit=5, dry_run=True)
    state["review_passed"] = True
    state["iteration"] = 1
    assert route_after_review(state) == "organize"


def test_route_after_review_revises_under_max_iterations():
    state = initial_state(["github"], limit=5, dry_run=True)
    state["review_passed"] = False
    state["iteration"] = 1
    state["plan"]["max_iterations"] = 2
    assert route_after_review(state) == "revise"


def test_route_after_review_flags_human_at_max_iterations():
    state = initial_state(["github"], limit=5, dry_run=True)
    state["review_passed"] = False
    state["iteration"] = 2
    state["plan"]["max_iterations"] = 2
    assert route_after_review(state) == "human_flag"


def test_calculate_weighted_score_uses_code_weights():
    score = calculate_weighted_score({
        "summary_quality": 8,
        "technical_depth": 6,
        "relevance": 9,
        "originality": 5,
        "formatting": 8,
    })
    assert score == 7.25


def test_parse_sources_rejects_unknown_source():
    assert parse_sources("github,rss") == ["github", "rss"]
    try:
        parse_sources("github,hackernews")
    except ValueError as error:
        assert "hackernews" in str(error)
    else:
        raise AssertionError("parse_sources should reject unsupported sources")


def test_build_articles_filters_deduplicates_and_matches_hook_schema(tmp_path):
    existing = {
        "id": "github-20260501-001",
        "source_url": "https://example.com/existing",
    }
    (tmp_path / "existing.json").write_text(json.dumps(existing), encoding="utf-8")

    analyses = [
        {
            "title": "Duplicate",
            "source": "github",
            "source_url": "https://example.com/existing",
            "collected_at": "2026-05-01T00:00:00Z",
            "summary": "A useful summary about an LLM agent framework and API.",
            "tags": ["llm"],
            "score": 8,
            "relevance_score": 0.9,
        },
        {
            "title": "Too Low",
            "source": "rss:Test Feed",
            "source_url": "https://example.com/low",
            "collected_at": "2026-05-01T00:00:00Z",
            "summary": "A useful summary about a model.",
            "tags": ["llm"],
            "score": 6,
            "relevance_score": 0.1,
        },
        {
            "title": "New",
            "source": "rss:Test Feed",
            "source_url": "https://example.com/new",
            "collected_at": "2026-05-01T00:00:00Z",
            "summary": "A useful summary about an LLM agent framework and API.",
            "tags": ["agent"],
            "score": 9,
            "relevance_score": 0.8,
            "audience": "advanced",
        },
    ]

    articles = build_articles(analyses, relevance_threshold=0.5, articles_dir=tmp_path)
    assert len(articles) == 1
    article = articles[0]
    assert article["title"] == "New"
    assert article["id"].startswith("rss:test-feed-")
    assert article["source_url"] == "https://example.com/new"
    assert article["status"] == "published"
    assert article["score"] == 9


def test_save_articles_writes_files_and_index(tmp_path):
    articles = [
        {
            "id": "github-20260501-001",
            "title": "Test",
            "source": "github",
            "source_url": "https://example.com/1",
            "url": "https://example.com/1",
            "summary": "A useful summary about an LLM agent framework and API.",
            "tags": ["llm"],
            "status": "published",
            "score": 8,
        }
    ]

    paths = save_articles(articles, articles_dir=tmp_path)
    assert len(paths) == 1
    assert paths[0].exists()
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index[0]["id"] == "github-20260501-001"


def test_write_pending_review_persists_outside_articles(tmp_path):
    path = write_pending_review(
        {"iterations_used": 2, "analyses": [], "last_feedback": "needs work"},
        pending_dir=tmp_path,
    )
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["iterations_used"] == 2


def test_organize_node_falls_back_to_default_articles_dir_when_state_value_is_none():
    result = organize_node({
        "plan": {"relevance_threshold": 0.5},
        "analyses": [],
        "articles_dir": None,
        "dry_run": True,
        "cost_tracker": {},
    })
    assert result["articles"] == []


def test_human_flag_node_falls_back_to_default_pending_dir_when_state_value_is_none():
    result = human_flag_node({
        "plan": {"max_iterations": 2},
        "iteration": 2,
        "review_feedback": "needs work",
        "analyses": [],
        "pending_review_dir": None,
        "dry_run": True,
    })
    assert result["needs_human_review"] is True


def test_enforce_run_policies_fails_on_human_flag():
    with pytest.raises(SystemExit, match="human_flag"):
        enforce_run_policies(
            {"needs_human_review": True, "published": 1},
            fail_on_human_flag=True,
        )


def test_enforce_run_policies_fails_when_published_below_minimum():
    with pytest.raises(SystemExit, match="below required minimum"):
        enforce_run_policies(
            {"needs_human_review": False, "published": 0},
            min_published=1,
        )
