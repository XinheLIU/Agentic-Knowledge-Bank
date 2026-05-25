"""Tests for workflows/organizer.py persistence of personal relevance fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflows.organizer import build_articles

pytestmark = pytest.mark.non_llm


def _base_analysis(**overrides) -> dict:
    base = {
        "title": "Test Article",
        "source": "github",
        "source_url": "https://example.com/test-1",
        "url": "https://example.com/test-1",
        "summary": "A sufficiently long summary for the test to pass validation requirements.",
        "tags": ["llm"],
        "score": 8,
        "relevance_score": 0.8,
        "category": "agent",
        "key_insight": "insight",
        "audience": "intermediate",
        "personal_fit_score": 0.85,
        "technical_depth_score": 0.75,
        "actionability_score": 0.90,
        "source_credibility_score": 0.80,
        "novelty_score": 0.65,
        "priority_score": 84,
        "reading_priority": "study-now",
        "relevance_reason": "Directly matches P0 agent topic",
        "suggested_action": "clone-and-study",
        "confidence": 0.82,
        "source_type": "repository",
        "learning_track": "agent-systems",
        "learning_tags": ["langgraph", "agent-harness"],
    }
    base.update(overrides)
    return base


class TestOrganizerPersistence:
    def test_preserves_learning_tags(self, tmp_path):
        articles = build_articles([_base_analysis()], 0.5, articles_dir=tmp_path)
        assert len(articles) == 1
        assert articles[0]["learning_tags"] == ["langgraph", "agent-harness"]

    def test_preserves_reading_priority(self, tmp_path):
        articles = build_articles([_base_analysis(reading_priority="save-for-context")], 0.5, articles_dir=tmp_path)
        assert articles[0]["reading_priority"] == "save-for-context"

    def test_preserves_priority_score(self, tmp_path):
        articles = build_articles([_base_analysis(priority_score=92)], 0.5, articles_dir=tmp_path)
        assert articles[0]["priority_score"] == 92

    def test_preserves_source_type(self, tmp_path):
        articles = build_articles([_base_analysis(source_type="tutorial")], 0.5, articles_dir=tmp_path)
        assert articles[0]["source_type"] == "tutorial"

    def test_preserves_learning_track(self, tmp_path):
        articles = build_articles([_base_analysis(learning_track="data-agents")], 0.5, articles_dir=tmp_path)
        assert articles[0]["learning_track"] == "data-agents"

    def test_preserves_component_scores(self, tmp_path):
        articles = build_articles([_base_analysis()], 0.5, articles_dir=tmp_path)
        assert articles[0]["personal_fit_score"] == 0.85
        assert articles[0]["technical_depth_score"] == 0.75
        assert articles[0]["actionability_score"] == 0.90
        assert articles[0]["source_credibility_score"] == 0.80
        assert articles[0]["novelty_score"] == 0.65

    def test_preserves_relevance_reason(self, tmp_path):
        articles = build_articles([_base_analysis(relevance_reason="Key for RAG study")], 0.5, articles_dir=tmp_path)
        assert articles[0]["relevance_reason"] == "Key for RAG study"

    def test_preserves_suggested_action(self, tmp_path):
        articles = build_articles([_base_analysis(suggested_action="deep-read")], 0.5, articles_dir=tmp_path)
        assert articles[0]["suggested_action"] == "deep-read"

    def test_preserves_confidence(self, tmp_path):
        articles = build_articles([_base_analysis(confidence=0.95)], 0.5, articles_dir=tmp_path)
        assert articles[0]["confidence"] == 0.95

    def test_safe_defaults_for_missing_fields(self, tmp_path):
        minimal = _base_analysis(
            source_url="https://example.com/minimal",
        )
        for key in [
            "personal_fit_score", "technical_depth_score", "actionability_score",
            "source_credibility_score", "novelty_score", "priority_score",
            "reading_priority", "relevance_reason", "suggested_action",
            "confidence", "source_type", "learning_track", "learning_tags",
        ]:
            minimal.pop(key, None)

        articles = build_articles([minimal], 0.5, articles_dir=tmp_path)
        assert len(articles) == 1
        assert articles[0]["reading_priority"] == "low-priority"
        assert articles[0]["source_type"] == "unknown"
        assert articles[0]["learning_track"] == "background"
        assert articles[0]["learning_tags"] == []
        assert articles[0]["suggested_action"] == "skim"
        assert articles[0]["priority_score"] == 0
        assert articles[0]["personal_fit_score"] == 0.0

    def test_existing_fields_unchanged(self, tmp_path):
        articles = build_articles([_base_analysis()], 0.5, articles_dir=tmp_path)
        a = articles[0]
        assert a["id"]
        assert a["title"] == "Test Article"
        assert a["source"] == "github"
        assert a["tags"] == ["llm"]
        assert a["score"] == 8
        assert a["relevance_score"] == 0.8
        assert a["category"] == "agent"
        assert a["status"] == "published"

    def test_clamps_out_of_range_component_scores(self, tmp_path):
        articles = build_articles([
            _base_analysis(
                source_url="https://example.com/clamp",
                personal_fit_score=1.5,
                technical_depth_score=-0.2,
                priority_score=200,
            )
        ], 0.5, articles_dir=tmp_path)
        a = articles[0]
        assert a["personal_fit_score"] == 1.0
        assert a["technical_depth_score"] == 0.0
        assert a["priority_score"] == 100

    def test_invalid_enum_defaults(self, tmp_path):
        articles = build_articles([
            _base_analysis(
                source_url="https://example.com/enum",
                reading_priority="super-urgent",
                source_type="vlog",
                learning_track="astro-physics",
                suggested_action="ignore",
            )
        ], 0.5, articles_dir=tmp_path)
        a = articles[0]
        assert a["reading_priority"] == "low-priority"
        assert a["source_type"] == "unknown"
        assert a["learning_track"] == "background"
        assert a["suggested_action"] == "skim"
