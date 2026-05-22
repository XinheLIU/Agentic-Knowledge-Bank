"""Tests for UI sources endpoints."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from ui.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_get_sources_lists_all(client, monkeypatch, tmp_path):
    """Test GET /api/sources lists configured sources."""
    # Mock RSS config
    mock_config = {
        "sources": [
            {"slug": "test1", "name": "Test 1", "url": "https://example.com/rss", "category": "general", "enabled": True, "per_source_limit": 5},
            {"slug": "test2", "name": "Test 2", "url": "https://example.com/rss2", "category": "news", "enabled": False, "per_source_limit": 3},
        ]
    }
    mock_config_path = tmp_path / "rss_sources.yaml"
    mock_config_path.write_text(yaml.dump(mock_config), encoding="utf-8")
    monkeypatch.setattr("ui.app.RSS_CONFIG", mock_config_path)
    # Mock knowledge dir
    monkeypatch.setattr("ui.app.KNOWLEDGE_DIR", tmp_path / "articles")
    (tmp_path / "articles").mkdir()

    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]["slug"] == "test1"
    assert data[0]["last_7d_count"] == 0


def test_get_sources_count_recent_only(client, monkeypatch, tmp_path):
    """Test last_7d_count only counts recent articles."""
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    # Create recent article
    recent_article = {
        "id": "test1-20260522-001",
        "title": "Recent",
        "source_url": "https://example.com",
        "collected_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }
    (articles_dir / "test1-20260522-001.json").write_text(json.dumps(recent_article), encoding="utf-8")
    # Create old article
    old_article = {
        "id": "test1-20260514-001",
        "title": "Old",
        "source_url": "https://example.com",
        "collected_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
    }
    (articles_dir / "test1-20260514-001.json").write_text(json.dumps(old_article), encoding="utf-8")
    # Mock config
    mock_config = {"sources": [{"slug": "test1", "name": "Test 1", "url": "https://example.com/rss"}]}
    mock_config_path = tmp_path / "rss_sources.yaml"
    mock_config_path.write_text(yaml.dump(mock_config), encoding="utf-8")
    monkeypatch.setattr("ui.app.RSS_CONFIG", mock_config_path)
    monkeypatch.setattr("ui.app.KNOWLEDGE_DIR", articles_dir)

    response = client.get("/api/sources")
    data = response.get_json()
    assert data[0]["last_7d_count"] == 1


def test_patch_toggles_enabled(client, monkeypatch, tmp_path):
    """Test PATCH /api/sources/<slug> toggles enabled state."""
    mock_config = {
        "sources": [
            {"slug": "test1", "name": "Test 1", "url": "https://example.com/rss", "enabled": True},
            {"slug": "test2", "name": "Test 2", "url": "https://example.com/rss2", "enabled": False},
        ]
    }
    mock_config_path = tmp_path / "rss_sources.yaml"
    mock_config_path.write_text(yaml.dump(mock_config), encoding="utf-8")
    monkeypatch.setattr("ui.app.RSS_CONFIG", mock_config_path)
    monkeypatch.setattr("ui.app.KNOWLEDGE_DIR", tmp_path / "articles")
    (tmp_path / "articles").mkdir()

    # Disable test1
    response = client.patch("/api/sources/test1", json={"enabled": False})
    assert response.status_code == 200
    data = response.get_json()
    assert next(src for src in data if src["slug"] == "test1")["enabled"] is False
    # Check file was updated
    updated_config = yaml.safe_load(mock_config_path.read_text(encoding="utf-8"))
    assert updated_config["sources"][0]["enabled"] is False

    # Enable test2
    response = client.patch("/api/sources/test2", json={"enabled": True})
    assert response.status_code == 200
    data = response.get_json()
    assert next(src for src in data if src["slug"] == "test2")["enabled"] is True


def test_patch_unknown_slug_404(client, monkeypatch, tmp_path):
    """Test PATCH on unknown slug returns 404."""
    mock_config = {"sources": [{"slug": "test1", "name": "Test 1", "url": "https://example.com/rss"}]}
    mock_config_path = tmp_path / "rss_sources.yaml"
    mock_config_path.write_text(yaml.dump(mock_config), encoding="utf-8")
    monkeypatch.setattr("ui.app.RSS_CONFIG", mock_config_path)
    monkeypatch.setattr("ui.app.KNOWLEDGE_DIR", tmp_path / "articles")
    (tmp_path / "articles").mkdir()

    response = client.patch("/api/sources/nonexistent", json={"enabled": True})
    assert response.status_code == 404


def test_patch_preserves_other_sources(client, monkeypatch, tmp_path):
    """Test PATCH doesn't modify other sources."""
    mock_config = {
        "sources": [
            {"slug": "test1", "name": "Test 1", "url": "https://example.com/rss", "enabled": True, "per_source_limit": 5},
            {"slug": "test2", "name": "Test 2", "url": "https://example.com/rss2", "enabled": True, "per_source_limit": 3, "category": "news"},
        ]
    }
    mock_config_path = tmp_path / "rss_sources.yaml"
    mock_config_path.write_text(yaml.dump(mock_config), encoding="utf-8")
    monkeypatch.setattr("ui.app.RSS_CONFIG", mock_config_path)
    monkeypatch.setattr("ui.app.KNOWLEDGE_DIR", tmp_path / "articles")
    (tmp_path / "articles").mkdir()

    response = client.patch("/api/sources/test1", json={"enabled": False})
    assert response.status_code == 200
    updated_config = yaml.safe_load(mock_config_path.read_text(encoding="utf-8"))
    test2 = next(src for src in updated_config["sources"] if src["slug"] == "test2")
    assert test2["enabled"] is True
    assert test2["per_source_limit"] == 3
    assert test2["category"] == "news"
