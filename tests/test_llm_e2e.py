"""Real-provider end-to-end workflow verification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from check_quality import evaluate_quality
from validate_json import validate_article
from workflows.graph import parse_sources, run_workflow

pytestmark = pytest.mark.llm_e2e


def _has_any_provider_credentials() -> bool:
    provider = os.getenv("LLM_PROVIDER", "qwen").lower()
    if provider == "deepseek":
        return bool(os.getenv("DEEPSEEK_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return bool(os.getenv("DASHSCOPE_API_KEY"))


@pytest.mark.skipif(not _has_any_provider_credentials(), reason="real LLM provider credentials required")
def test_real_llm_workflow_publishes_valid_articles(tmp_path):
    articles_dir = tmp_path / "articles"
    pending_review_dir = tmp_path / "pending_review"

    stats = run_workflow(
        sources=parse_sources("github,rss"),
        limit=3,
        dry_run=False,
        articles_dir=articles_dir,
        pending_review_dir=pending_review_dir,
    )

    assert stats["needs_human_review"] is False
    assert stats["published"] >= 1

    article_files = sorted(path for path in articles_dir.glob("*.json") if path.name != "index.json")
    assert article_files

    for article_file in article_files:
        data = json.loads(article_file.read_text(encoding="utf-8"))
        assert validate_article(data) == []
        report = evaluate_quality(str(article_file), data)
        assert report.grade in {"A", "B"}
