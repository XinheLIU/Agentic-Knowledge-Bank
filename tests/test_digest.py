"""Tests for workflows/digest.py — daily digest builder and email sender."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflows import digest as digest_module
from workflows.digest import build_digest, send_email

pytestmark = pytest.mark.non_llm


def _write_article(articles_dir: Path, **fields) -> None:
    base = {
        "id": fields.get("id", "x-20260623-001"),
        "title": "Untitled",
        "source_url": "https://example.com",
        "summary": "summary text",
        "key_insight": "the insight",
        "collected_at": "2026-06-23T08:00:00+00:00",
        "reading_priority": "study-now",
        "priority_score": 50,
        "learning_track": "agent-systems",
        "learning_tags": ["langgraph"],
        "suggested_action": "deep-read",
    }
    base.update(fields)
    (articles_dir / f"{base['id']}.json").write_text(
        json.dumps(base, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def articles_dir(tmp_path):
    d = tmp_path / "articles"
    d.mkdir()
    return d


class TestBuildDigest:
    def test_filters_by_date_and_priority(self, articles_dir):
        _write_article(articles_dir, id="a", reading_priority="study-now", priority_score=90)
        _write_article(articles_dir, id="b", reading_priority="skim", priority_score=80)
        _write_article(
            articles_dir, id="c", reading_priority="study-now",
            collected_at="2026-06-22T08:00:00+00:00", title="Yesterday",
        )
        out = build_digest(articles_dir, since="2026-06-23")
        assert "共 1 条高优先级" in out
        assert "Yesterday" not in out  # wrong date excluded

    def test_sorted_by_score_desc(self, articles_dir):
        _write_article(articles_dir, id="low", title="LowScore", priority_score=40)
        _write_article(articles_dir, id="high", title="HighScore", priority_score=95)
        out = build_digest(articles_dir, since="2026-06-23")
        assert out.index("HighScore") < out.index("LowScore")

    def test_groups_by_priority(self, articles_dir):
        _write_article(articles_dir, id="s", title="StudyItem", reading_priority="study-now")
        _write_article(articles_dir, id="c", title="ContextItem", reading_priority="save-for-context")
        out = build_digest(articles_dir, since="2026-06-23")
        assert "## Study now" in out
        assert "## Save for context" in out
        # study-now group renders before save-for-context (priority order)
        assert out.index("## Study now") < out.index("## Save for context")

    def test_renders_source_url_as_link(self, articles_dir):
        _write_article(articles_dir, id="a", title="Repo", source_url="https://gh.com/x")
        out = build_digest(articles_dir, since="2026-06-23")
        assert "[Repo](https://gh.com/x)" in out

    def test_empty_day_returns_valid_body(self, articles_dir):
        out = build_digest(articles_dir, since="2026-06-23")
        assert "今日没有高优先级条目" in out

    def test_missing_dir_is_graceful(self, tmp_path):
        out = build_digest(tmp_path / "nope", since="2026-06-23")
        assert "今日没有高优先级条目" in out


class TestSendEmail:
    def test_skips_without_credentials(self):
        sent = send_email("subj", "body", {"email": "", "password": ""})
        assert sent is False

    def test_sends_when_configured(self, monkeypatch):
        calls = {}

        class FakeSMTP:
            def __init__(self, host, port):
                calls["host"] = host
                calls["port"] = port

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                calls["starttls"] = True

            def login(self, email, password):
                calls["login"] = (email, password)

            def send_message(self, msg):
                calls["to"] = msg["To"]
                calls["subject"] = msg["Subject"]

        monkeypatch.setattr(digest_module.smtplib, "SMTP", FakeSMTP)
        settings = {
            "host": "smtp.test",
            "port": 587,
            "email": "me@test.com",
            "password": "pw",
            "recipients": "a@test.com, b@test.com",
        }
        sent = send_email("subj", "body", settings)
        assert sent is True
        assert calls["starttls"] is True
        assert calls["login"] == ("me@test.com", "pw")
        assert calls["to"] == "a@test.com, b@test.com"
        assert calls["subject"] == "subj"

    def test_recipients_default_to_sender(self, monkeypatch):
        captured = {}

        class FakeSMTP:
            def __init__(self, *a):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def send_message(self, msg):
                captured["to"] = msg["To"]

        monkeypatch.setattr(digest_module.smtplib, "SMTP", FakeSMTP)
        send_email("s", "b", {"host": "h", "port": 1, "email": "me@x.com", "password": "p", "recipients": ""})
        assert captured["to"] == "me@x.com"
