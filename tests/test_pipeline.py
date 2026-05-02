"""Tests for pipeline/pipeline.py"""

import json
from pathlib import Path

import pytest

from pipeline import step_organize, step_save


class TestStepOrganize:
    def test_deduplicates_by_source_url(self, tmp_path, monkeypatch):
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        monkeypatch.setattr("pipeline.ARTICLES_DIR", articles_dir)

        # Existing article
        existing = {
            "id": "github-20260501-001",
            "title": "Existing",
            "source_url": "http://example.com/existing",
        }
        with open(articles_dir / "existing.json", "w", encoding="utf-8") as f:
            json.dump(existing, f)

        items = [
            {
                "id": "github-20260501-002",
                "title": "Duplicate",
                "source_url": "http://example.com/existing",
                "author": "alice",
                "published_at": "2026-05-01T00:00:00Z",
                "collected_at": "2026-05-01T00:00:00Z",
                "summary": "A summary that is long enough to pass validation",
                "score": 7,
                "tags": ["llm"],
                "audience": "intermediate",
                "status": "review",
            },
            {
                "id": "github-20260501-003",
                "title": "New",
                "source_url": "http://example.com/new",
                "author": "bob",
                "published_at": "2026-05-01T00:00:00Z",
                "collected_at": "2026-05-01T00:00:00Z",
                "summary": "Another summary that is definitely long enough",
                "score": 8,
                "tags": ["agent"],
                "audience": "advanced",
                "status": "review",
            },
        ]

        result = step_organize(items)
        assert len(result) == 1
        assert result[0]["title"] == "New"

    def test_standardizes_fields(self, monkeypatch, tmp_path):
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        monkeypatch.setattr("pipeline.ARTICLES_DIR", articles_dir)

        items = [
            {
                "id": "rss-20260501-001",
                "title": "Test",
                "source_url": "http://example.com/test",
                "author": "alice",
                "published_at": "2026-05-01T00:00:00Z",
                "collected_at": "2026-05-01T00:00:00Z",
                "summary": "Summary text that is long enough for validation rules",
                "score": 15,
                "tags": ["llm", "rag"],
                "audience": "intermediate",
                "status": "review",
            }
        ]

        result = step_organize(items)
        assert len(result) == 1
        article = result[0]
        assert article["score"] == 10  # clamped to max
        assert article["source"] == "unknown"  # default
        assert "updated_at" in article

    def test_clamps_score_to_range(self, monkeypatch, tmp_path):
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        monkeypatch.setattr("pipeline.ARTICLES_DIR", articles_dir)

        items = [
            {
                "id": "rss-20260501-001",
                "title": "Low",
                "source_url": "http://example.com/low",
                "author": "a",
                "published_at": "",
                "collected_at": "",
                "summary": "A sufficiently long summary for the test to pass",
                "score": 0,
                "tags": ["llm"],
                "audience": "beginner",
                "status": "draft",
            },
            {
                "id": "rss-20260501-002",
                "title": "High",
                "source_url": "http://example.com/high",
                "author": "b",
                "published_at": "",
                "collected_at": "",
                "summary": "Another sufficiently long summary for the test to pass",
                "score": 99,
                "tags": ["agent"],
                "audience": "advanced",
                "status": "published",
            },
        ]

        result = step_organize(items)
        assert result[0]["score"] == 1
        assert result[1]["score"] == 10


class TestStepSave:
    def test_saves_files(self, monkeypatch, tmp_path):
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        monkeypatch.setattr("pipeline.ARTICLES_DIR", articles_dir)

        items = [
            {
                "id": "github-20260501-001",
                "title": "Test Article",
                "source": "github",
                "source_url": "http://example.com/1",
            }
        ]

        paths = step_save(items, dry_run=False)
        assert len(paths) == 1
        assert paths[0].exists()
        with open(paths[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["title"] == "Test Article"

    def test_dry_run_does_not_write(self, monkeypatch, tmp_path):
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        monkeypatch.setattr("pipeline.ARTICLES_DIR", articles_dir)

        items = [
            {
                "id": "github-20260501-001",
                "title": "Test Article",
                "source": "github",
                "source_url": "http://example.com/1",
            }
        ]

        paths = step_save(items, dry_run=True)
        assert len(paths) == 1
        assert not paths[0].exists()
