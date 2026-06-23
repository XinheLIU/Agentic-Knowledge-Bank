"""Tests for workflows/prompts.py — the externalized prompt loader.

Verifies the loader's provider-override/fallback logic and that the migrated
templates still render faithfully (no leftover placeholders, key constraint
lines intact).
"""

from __future__ import annotations

import pytest

from workflows import prompts as prompts_module
from workflows.prompts import load_prompt, render

pytestmark = pytest.mark.non_llm


ANALYZER_MAPPING = {
    "profile_text": "<profile>",
    "title": "Some Repo",
    "source": "github",
    "url": "https://example.com/x",
    "description": "a description",
    "learning_tags": "langgraph, agent-harness",
}
REVIEWER_MAPPING = {"profile_text": "<profile>", "analyses_json": "[]"}
REVISER_MAPPING = {"feedback": "fix depth", "analyses_json": "[]"}


@pytest.fixture(autouse=True)
def _clear_cache():
    prompts_module._cache.clear()
    yield
    prompts_module._cache.clear()


class TestRenderNoLeftovers:
    @pytest.mark.parametrize(
        "name,mapping",
        [
            ("analyzer", ANALYZER_MAPPING),
            ("reviewer", REVIEWER_MAPPING),
            ("reviser", REVISER_MAPPING),
        ],
    )
    def test_no_leftover_placeholders(self, name, mapping):
        rendered = render(name, mapping)
        # Every $placeholder must have been substituted. The templates contain
        # literal JSON braces but no literal "$", so none should remain.
        assert "$" not in rendered
        # Inputs were actually injected.
        for value in mapping.values():
            assert value in rendered

    def test_missing_placeholder_raises(self):
        with pytest.raises(KeyError):
            render("analyzer", {"profile_text": "x"})  # missing title etc.


class TestFaithfulExtraction:
    """Golden checks that the migration preserved the exact constraint lines."""

    def test_analyzer_key_constraints(self):
        rendered = render("analyzer", ANALYZER_MAPPING)
        assert 'category 必须是单个字符串' in rendered
        assert 'reading_priority 至少为 save-for-context' in rendered
        assert 'P0 必学主题' in rendered
        assert 'learning_tags 从允许列表选取: langgraph, agent-harness' in rendered

    def test_reviewer_dimensions(self):
        rendered = render("reviewer", REVIEWER_MAPPING)
        for dim in ("summary_quality", "technical_depth", "personal_relevance",
                    "actionability", "formatting"):
            assert dim in rendered
        assert '不确定但可能相关的内容不应被标记为 skip' in rendered

    def test_reviser_preserves_provenance_rule(self):
        rendered = render("reviser", REVISER_MAPPING)
        assert '不要删除 source_url、id、title、source、collected_at' in rendered
        assert 'fix depth' in rendered

    def test_system_prompts_present(self):
        assert load_prompt("reviewer_system").strip()
        assert load_prompt("reviser_system").strip()


class TestProviderFallback:
    def test_provider_override_wins(self, tmp_path, monkeypatch):
        monkeypatch.setattr(prompts_module, "PROMPTS_DIR", tmp_path)
        (tmp_path / "demo.txt").write_text("generic $x", encoding="utf-8")
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "demo.txt").write_text("acme $x", encoding="utf-8")

        assert load_prompt("demo", provider="acme") == "acme $x"
        assert load_prompt("demo", provider="other") == "generic $x"

    def test_missing_template_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(prompts_module, "PROMPTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            load_prompt("nope", provider="acme")

    def test_provider_defaults_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setattr(prompts_module, "PROMPTS_DIR", tmp_path)
        (tmp_path / "demo.txt").write_text("generic", encoding="utf-8")
        (tmp_path / "deepseek").mkdir()
        (tmp_path / "deepseek" / "demo.txt").write_text("deepseek", encoding="utf-8")
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        assert load_prompt("demo") == "deepseek"
