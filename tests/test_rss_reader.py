"""Tests for pipeline/rss_reader.py"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rss_reader import collect_rss


class TestCollectRss:
    def test_collects_entries_from_feed(self, tmp_path, mocker):
        config = tmp_path / "rss_sources.yaml"
        config.write_text(
            """
sources:
  - name: "Test Feed"
    url: "http://example.com/feed.xml"
    category: "test"
    enabled: true
""",
            encoding="utf-8",
        )

        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, d="": {
            "title": "Test Title",
            "link": "http://example.com/post/1",
            "summary": "Test summary",
        }.get(k, d)

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        mocker.patch("rss_reader.RSS_CONFIG", config)
        mocker.patch("rss_reader.feedparser.parse", return_value=mock_feed)

        # Mock httpx.Client to return empty text (feedparser.parse receives text)
        mock_response = MagicMock()
        mock_response.text = "<rss></rss>"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mocker.patch("rss_reader.httpx.Client", return_value=mock_client)

        items = collect_rss(limit=5)

        assert len(items) == 1
        assert items[0]["title"] == "Test Title"
        assert items[0]["source_url"] == "http://example.com/post/1"
        assert items[0]["source"] == "rss:Test Feed"
        assert items[0]["category"] == "test"

    def test_skips_entries_without_title_or_link(self, tmp_path, mocker):
        config = tmp_path / "rss_sources.yaml"
        config.write_text(
            """
sources:
  - name: "Test Feed"
    url: "http://example.com/feed.xml"
    category: "test"
    enabled: true
""",
            encoding="utf-8",
        )

        mock_entry_empty = MagicMock()
        mock_entry_empty.get.side_effect = lambda k, d="": d

        mock_entry_valid = MagicMock()
        mock_entry_valid.get.side_effect = lambda k, d="": {
            "title": "Valid Title",
            "link": "http://example.com/post/2",
            "summary": "",
        }.get(k, d)

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry_empty, mock_entry_valid]

        mocker.patch("rss_reader.RSS_CONFIG", config)
        mocker.patch("rss_reader.feedparser.parse", return_value=mock_feed)

        mock_response = MagicMock()
        mock_response.text = "<rss></rss>"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mocker.patch("rss_reader.httpx.Client", return_value=mock_client)

        items = collect_rss(limit=5)
        assert len(items) == 1
        assert items[0]["title"] == "Valid Title"

    def test_returns_empty_when_config_missing(self, mocker):
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = False
        mocker.patch("rss_reader.RSS_CONFIG", mock_path)
        items = collect_rss(limit=5)
        assert items == []

    def test_respects_limit_across_sources(self, tmp_path, mocker):
        config = tmp_path / "rss_sources.yaml"
        config.write_text(
            """
sources:
  - name: "Feed A"
    url: "http://a.com/feed.xml"
    category: "test"
    enabled: true
  - name: "Feed B"
    url: "http://b.com/feed.xml"
    category: "test"
    enabled: true
""",
            encoding="utf-8",
        )

        def make_entry(title, link):
            e = MagicMock()
            e.get.side_effect = lambda k, d="": {
                "title": title, "link": link, "summary": ""
            }.get(k, d)
            return e

        mock_feed = MagicMock()
        mock_feed.entries = [
            make_entry(f"Title {i}", f"http://example.com/{i}")
            for i in range(10)
        ]

        mocker.patch("rss_reader.RSS_CONFIG", config)
        mocker.patch("rss_reader.feedparser.parse", return_value=mock_feed)

        mock_response = MagicMock()
        mock_response.text = "<rss></rss>"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mocker.patch("rss_reader.httpx.Client", return_value=mock_client)

        items = collect_rss(limit=3)
        assert len(items) == 3
