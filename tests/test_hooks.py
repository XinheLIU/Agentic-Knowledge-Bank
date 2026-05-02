"""Tests for hooks/validate_json.py and hooks/check_quality.py"""

import json
from pathlib import Path

import pytest

from check_quality import evaluate_quality
from validate_json import validate_article


class TestValidateArticle:
    def test_valid_article_passes(self):
        data = {
            "id": "github-20260501-001",
            "title": "A Valid Article",
            "source_url": "https://github.com/example/repo",
            "summary": "This is a sufficiently long summary that explains what the article is about.",
            "tags": ["llm", "agent"],
            "status": "review",
            "score": 7,
            "audience": "intermediate",
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
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
        }
        errors = validate_article(data)
        assert any("ID 格式错误" in e for e in errors)

    def test_empty_title(self):
        data = {
            "id": "github-20260501-001",
            "title": "   ",
            "source_url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
        }
        errors = validate_article(data)
        assert any("标题不能为空" in e for e in errors)

    def test_short_summary(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "summary": "Too short",
            "tags": ["llm"],
            "status": "review",
        }
        errors = validate_article(data)
        assert any("摘要太短" in e for e in errors)

    def test_invalid_status(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "invalid-status",
        }
        errors = validate_article(data)
        assert any("无效的 status" in e for e in errors)

    def test_score_out_of_range(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "score": 15,
        }
        errors = validate_article(data)
        assert any("score 超出范围" in e for e in errors)

    def test_invalid_audience(self):
        data = {
            "id": "github-20260501-001",
            "title": "Test",
            "source_url": "https://example.com",
            "summary": "A sufficiently long summary for the test to pass.",
            "tags": ["llm"],
            "status": "review",
            "audience": "expert",
        }
        errors = validate_article(data)
        assert any("无效的 audience" in e for e in errors)


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
        }
        report = evaluate_quality("test.json", data)
        assert report.grade == "A"
        assert report.total_score >= 80

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
        assert report.total_score < 60

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
        }
        report = evaluate_quality("test.json", data)
        assert report.grade in ("A", "B")
        assert report.total_score >= 60

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
