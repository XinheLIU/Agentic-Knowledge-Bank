"""Tests for workflow nodes with mocked LLM and HTTP boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from workflows.analyzer import analyze_node
from workflows.collector import collect_github
from workflows.graph import build_graph, initial_state
from workflows.reviewer import review_node
from workflows.reviser import revise_node

pytestmark = pytest.mark.non_llm


def test_analyze_node_success(mocker):
    mocker.patch(
        "workflows.analyzer.chat_json_with_model",
        return_value=(
            {
                "summary": "这是一段足够长的中文技术摘要，描述模型能力、应用边界和关键价值。",
                "tags": ["llm", "agent"],
                "relevance_score": 0.8,
                "category": "agent",
                "key_insight": "重点在于工作流闭环。",
                "score": 8,
                "audience": "advanced",
            },
            MagicMock(prompt_tokens=10, completion_tokens=5),
            "qwen-plus",
        ),
    )
    mocker.patch(
        "workflows.analyzer.accumulate_usage",
        return_value={"prompt_tokens": 10, "completion_tokens": 5, "total_cost_usd": 0.01},
    )

    state = {
        "sources": [
            {
                "title": "Repo",
                "source": "github",
                "source_url": "https://example.com/repo",
                "raw_description": "desc",
            }
        ],
        "cost_tracker": {},
    }
    result = analyze_node(state)
    assert len(result["analyses"]) == 1
    assert result["analyses"][0]["status"] == "review"
    assert result["analyses"][0]["tags"] == ["llm", "agent"]


def test_analyze_node_falls_back_on_llm_error(mocker):
    mocker.patch("workflows.analyzer.chat_json_with_model", side_effect=RuntimeError("boom"))

    state = {
        "sources": [
            {
                "title": "Repo",
                "source": "github",
                "source_url": "https://example.com/repo",
                "raw_description": "short desc",
            }
        ],
        "cost_tracker": {},
    }
    result = analyze_node(state)
    assert result["analyses"][0]["status"] == "draft"
    assert result["analyses"][0]["score"] == 1
    assert result["analyses"][0]["relevance_score"] == 0.0


def test_review_node_success(mocker):
    mocker.patch(
        "workflows.reviewer.chat_json_with_model",
        return_value=(
            {
                "scores": {
                    "summary_quality": 8,
                    "technical_depth": 8,
                    "relevance": 9,
                    "originality": 7,
                    "formatting": 8,
                },
                "feedback": "ok",
                "weak_dimensions": ["originality"],
            },
            MagicMock(prompt_tokens=10, completion_tokens=5),
            "qwen-plus",
        ),
    )
    mocker.patch(
        "workflows.reviewer.accumulate_usage",
        return_value={"prompt_tokens": 10, "completion_tokens": 5, "total_cost_usd": 0.01},
    )

    result = review_node({"analyses": [{"title": "x"}], "iteration": 0, "cost_tracker": {}})
    assert result["review_passed"] is True
    assert result["iteration"] == 1
    assert "[弱项:" in result["review_feedback"]


def test_review_node_auto_passes_on_llm_error(mocker):
    mocker.patch("workflows.reviewer.chat_json_with_model", side_effect=RuntimeError("boom"))
    result = review_node({"analyses": [{"title": "x"}], "iteration": 0, "cost_tracker": {}})
    assert result["review_passed"] is True
    assert "自动通过" in result["review_feedback"]


def test_revise_node_success(mocker):
    mocker.patch(
        "workflows.reviser.chat_json_with_model",
        return_value=(
            [{"title": "updated", "summary": "new summary"}],
            MagicMock(prompt_tokens=10, completion_tokens=5),
            "qwen-plus",
        ),
    )
    mocker.patch(
        "workflows.reviser.accumulate_usage",
        return_value={"prompt_tokens": 10, "completion_tokens": 5, "total_cost_usd": 0.01},
    )

    result = revise_node(
        {
            "analyses": [{"title": "old"}],
            "review_feedback": "improve summary",
            "cost_tracker": {},
        }
    )
    assert result["analyses"][0]["title"] == "updated"


def test_revise_node_skips_without_feedback():
    result = revise_node({"analyses": [{"title": "old"}], "review_feedback": "", "cost_tracker": {}})
    assert "analyses" not in result


def test_collect_github_success(mocker):
    response = MagicMock()
    response.json.return_value = {
        "items": [
            {
                "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "owner": {"login": "owner"},
                "pushed_at": "2026-05-01T00:00:00Z",
                "description": "desc",
                "stargazers_count": 100,
                "forks_count": 10,
                "language": "Python",
                "topics": ["llm"],
            }
        ]
    }
    response.raise_for_status.return_value = None

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.get.return_value = response
    mocker.patch("workflows.collector.httpx.Client", return_value=client)

    items = collect_github(limit=1)
    assert len(items) == 1
    assert items[0]["source"] == "github"
    assert items[0]["source_url"] == "https://github.com/owner/repo"


def test_collect_github_failure_returns_empty(mocker):
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.get.side_effect = httpx.ConnectError("down")
    mocker.patch("workflows.collector.httpx.Client", return_value=client)
    assert collect_github(limit=1) == []


def test_build_graph_invokes_with_mocked_nodes(mocker, tmp_path):
    mocker.patch("workflows.graph.planner_node", return_value={"plan": {"per_source_limit": 1, "relevance_threshold": 0.5, "max_iterations": 1, "strategy": "lite", "rationale": ""}})
    mocker.patch("workflows.graph.collect_node", return_value={"sources": [{"title": "x", "source_url": "https://example.com/x", "source": "github", "summary": "s"}]})
    mocker.patch("workflows.graph.analyze_node", return_value={"analyses": [{"title": "x", "source": "github", "source_url": "https://example.com/x", "summary": "A sufficiently long summary for validation.", "tags": ["llm"], "score": 8, "relevance_score": 0.8, "status": "review"}]})
    mocker.patch("workflows.graph.review_node", return_value={"review_passed": True, "review_feedback": "", "iteration": 1, "cost_tracker": {}})
    mocker.patch("workflows.graph.organize_node", return_value={"articles": [{"id": "github-20260506-001"}], "cost_tracker": {}})

    app = build_graph().compile()
    result = app.invoke(
        initial_state(
            sources=["github"],
            limit=1,
            dry_run=True,
            articles_dir=tmp_path / "articles",
            pending_review_dir=tmp_path / "pending",
        )
    )
    assert result["review_passed"] is True
    assert result["articles"][0]["id"] == "github-20260506-001"
