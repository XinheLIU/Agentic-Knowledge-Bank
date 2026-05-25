"""Tests for hooks/validate_json.py and hooks/check_quality.py"""

import json
from pathlib import Path

import pytest

from check_quality import evaluate_quality
from validate_json import validate_article

pytestmark = pytest.mark.non_llm


class TestValidateArticle:
    def test_valid_article_passes(self):
        data = {
            "id": "github-20260501-001",
            "title": "A Valid Article",
            "source_url": "https://github.com/example/repo",
            "url": "https://github.com/example/repo",
            "summary": "This is a sufficiently long summary that explains what the article is about.",
            "tags": ["llm", "agent"],
            "status": "review",
            "score": 7,
            "audience": "intermediate",
            "key_insight": "A key insight.",
            "category": "llm",
            "relevance_score": 0.8,
        }
        errors = validate_article(data)
        assert errors == []

    def test_missing_required_fields(self):
        data = {}
        errors = validate_article(data)
        assert len(errors) >= 1
        assert any("缺少必填字段" in e for e in errors)

    def test_bad_id_format(self):
        data = {
            "id": "bad-id",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("ID 格式错误" in e for e in errors)

    def test_empty_title(self):
        data = {
            "id": "github-20260501-001",
            "title": "   ",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("标题不能为空" in e for e in errors)

    def test_short_summary(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "Too short",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("摘要太短" in e for e in errors)

    def test_invalid_status(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "invalid-status",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("无效的 status" in e for e in errors)

    def test_score_out_of_range(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "score": 15,
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("score 超出范围" in e for e in errors)

    def test_invalid_audience(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "audience": "expert",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("无效的 audience" in e for e in errors)

    def test_id_with_colon_rejected(self):
        data = {
            "id": "rss:reddit-ml-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("禁止冒号" in e for e in errors)

    def test_invalid_category_rejected(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "invalid",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert any("无效的 category" in e for e in errors)

    def test_author_and_published_at_may_be_null(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "author": None,
            "published_at": None,
        }
        errors = validate_article(data)
        assert errors == []


class TestFixtures:
    """Committed JSON under tests/fixtures/ (not under knowledge/)."""

    def test_example_article_fixture_passes_hooks(self):
        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "articles"
            / "example-published.json"
        )
        data = json.loads(fixture.read_text(encoding="utf-8"))
        assert validate_article(data) == []
        report = evaluate_quality(str(fixture), data)
        assert report.grade in ("A", "B")


class TestEvaluateQuality:
    def test_high_quality_article_gets_a(self):
        data = {
            "id": "github-20260501-001",
            "title": "Amazing LLM Framework",
            "source_url": "https://github.com/example/repo",
            "summary": (
                "This is a comprehensive summary about a new transformer-based model "
                "that achieves state-of-the-art results on multiple benchmarks using "
                "innovative training techniques and efficient inference APIs."
            ),
            "tags": ["llm", "agent"],
            "status": "review",
            "score": 9,
            "updated_at": "2026-05-01T00:00:00Z",
            "personal_fit_score": 0.9,
            "technical_depth_score": 0.85,
            "reading_priority": "study-now",
            "relevance_reason": "Core P0 topic",
            "suggested_action": "clone-and-study",
            "source_type": "repository",
            "learning_track": "agent-systems",
        }
        report = evaluate_quality("test.json", data)
        assert report.grade == "A"
        assert report.total_score >= 90

    def test_low_quality_article_gets_c(self):
        data = {
            "id": "github-20260501-001",
            "title": "x",
            "source_url": "https://github.com/example/repo",
            "summary": "short",
            "tags": [],
            "status": "draft",
            "score": 1,
        }
        report = evaluate_quality("test.json", data)
        assert report.grade == "C"
        assert report.total_score < 70

    def test_medium_quality_article_gets_b(self):
        data = {
            "id": "github-20260501-001",
            "title": "A decent project",
            "source_url": "https://github.com/example/repo",
            "summary": "This project provides a useful API for language model inference and training.",
            "tags": ["llm"],
            "status": "published",
            "score": 6,
            "updated_at": "2026-05-01T00:00:00Z",
            "reading_priority": "skim",
            "relevance_reason": "Background context",
            "source_type": "blog",
            "learning_track": "background",
        }
        report = evaluate_quality("test.json", data)
        assert report.grade in ("A", "B")
        assert report.total_score >= 70

    def test_hollow_words_penalty(self):
        data = {
            "id": "github-20260501-001",
            "title": "A groundbreaking revolutionary project",
            "source_url": "https://github.com/example/repo",
            "summary": "This is a world-class disruptive innovation that leverages synergy.",
            "tags": ["llm"],
            "status": "review",
            "score": 5,
            "updated_at": "2026-05-01T00:00:00Z",
        }
        report = evaluate_quality("test.json", data)
        hollow_dim = next(d for d in report.dimensions if d.name == "空洞词检测")
        assert hollow_dim.score < 15
        assert "groundbreaking" in hollow_dim.details or "revolutionary" in hollow_dim.details


class TestValidateNewFields:
    def test_valid_reading_priority(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "reading_priority": "study-now",
        }
        errors = validate_article(data)
        assert not any("reading_priority" in e for e in errors)

    def test_invalid_reading_priority(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "reading_priority": "urgent",
        }
        errors = validate_article(data)
        assert any("无效的 reading_priority" in e for e in errors)

    def test_valid_source_type(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "source_type": "repository",
        }
        errors = validate_article(data)
        assert not any("source_type" in e for e in errors)

    def test_invalid_source_type(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "source_type": "vlog",
        }
        errors = validate_article(data)
        assert any("无效的 source_type" in e for e in errors)

    def test_component_score_out_of_range(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "personal_fit_score": 1.5,
        }
        errors = validate_article(data)
        assert any("personal_fit_score 超出范围" in e for e in errors)

    def test_priority_score_out_of_range(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "priority_score": 150,
        }
        errors = validate_article(data)
        assert any("priority_score 超出范围" in e for e in errors)

    def test_historical_article_without_new_fields_still_valid(self):
        data = {
            "id": "github-20260501-001",
            "title": "Old Article",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "published",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
        }
        errors = validate_article(data)
        assert errors == []

    def test_learning_tags_must_be_list(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "learning_tags": "not-a-list",
        }
        errors = validate_article(data)
        assert any("learning_tags 应为列表" in e for e in errors)

    def test_valid_learning_track(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "learning_track": "agent-systems",
        }
        errors = validate_article(data)
        assert not any("learning_track" in e for e in errors)

    def test_invalid_learning_track(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "key_insight": "insight",
            "category": "llm",
            "relevance_score": 0.5,
            "learning_track": "astro-physics",
        }
        errors = validate_article(data)
        assert any("无效的 learning_track" in e for e in errors)


class TestPersonalRelevanceQuality:
    def test_high_personal_fit_article_gets_high_quality(self):
        data = {
            "id": "github-20260501-001",
            "title": "LangGraph Agent Framework",
            "source_url": "https://github.com/example/repo",
            "summary": (
                "This repository provides a comprehensive LangGraph agent framework "
                "with tool-use integration, MCP support, and production-ready evaluation "
                "pipelines for multi-agent systems."
            ),
            "tags": ["agent", "tool-use"],
            "status": "published",
            "score": 9,
            "updated_at": "2026-05-01T00:00:00Z",
            "personal_fit_score": 0.92,
            "technical_depth_score": 0.88,
            "reading_priority": "study-now",
            "relevance_reason": "Direct P0 match: agent engineering with LangGraph",
            "suggested_action": "clone-and-study",
            "source_type": "repository",
            "learning_track": "agent-systems",
            "learning_tags": ["langgraph", "agent-harness"],
        }
        report = evaluate_quality("test.json", data)
        assert report.grade == "A"
        personal_dim = next(d for d in report.dimensions if d.name == "个人相关性")
        assert personal_dim.score >= 12

    def test_generic_low_priority_article_lower_quality(self):
        data = {
            "id": "github-20260501-001",
            "title": "Generic AI News",
            "source_url": "https://example.com/news",
            "summary": "This is a generic news article about AI industry trends and market forecasts.",
            "tags": ["llm"],
            "status": "published",
            "score": 3,
            "updated_at": "2026-05-01T00:00:00Z",
        }
        report = evaluate_quality("test.json", data)
        personal_dim = next(d for d in report.dimensions if d.name == "个人相关性")
        assert personal_dim.score == 0

    def test_learning_tags_improve_tag_score(self):
        data_no_learning = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass validation requirements.",
            "tags": ["llm"],
            "status": "published",
            "score": 5,
        }
        data_with_learning = {
            **data_no_learning,
            "learning_tags": ["langgraph", "agent-harness"],
        }
        report_no = evaluate_quality("test.json", data_no_learning)
        report_with = evaluate_quality("test.json", data_with_learning)
        tags_no = next(d for d in report_no.dimensions if d.name == "标签精度")
        tags_with = next(d for d in report_with.dimensions if d.name == "标签精度")
        assert tags_with.score > tags_no.score
