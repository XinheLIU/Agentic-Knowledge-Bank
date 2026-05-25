"""Tests for workflows/analyzer.py normalization logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from workflows.analyzer import (
    VALID_BROAD_TAGS,
    VALID_LEARNING_TAGS,
    _apply_rule_caps,
    _check_focus_match,
    _clamp,
    _fallback_analysis,
    _normalize_learning_tags,
    _normalize_learning_track,
    _normalize_reading_priority,
    _normalize_source_type,
    _normalize_suggested_action,
    _normalize_tags,
    analyze_item,
)
from workflows.relevance_profile import DEFAULT_PROFILE

pytestmark = pytest.mark.non_llm


class TestClamp:
    @pytest.mark.parametrize("value,lo,hi,expected", [
        (0.5, 0.0, 1.0, 0.5),
        (-0.1, 0.0, 1.0, 0.0),
        (1.5, 0.0, 1.0, 1.0),
        (50, 0, 100, 50),
        (-10, 0, 100, 0),
        (200, 0, 100, 100),
    ])
    def test_clamp(self, value, lo, hi, expected):
        assert _clamp(value, lo, hi) == expected


class TestNormalizeTags:
    def test_valid_tags(self):
        assert _normalize_tags(["llm", "agent"]) == ["llm", "agent"]

    def test_invalid_tags_fallback(self):
        assert _normalize_tags(["invalid"]) == ["llm"]

    def test_empty_list_fallback(self):
        assert _normalize_tags([]) == ["llm"]

    def test_non_list_fallback(self):
        assert _normalize_tags("not a list") == ["llm"]

    def test_max_three_tags(self):
        assert len(_normalize_tags(["llm", "agent", "rag", "mcp"])) <= 3


class TestNormalizeLearningTags:
    def test_valid_learning_tags(self):
        assert _normalize_learning_tags(["langgraph", "agent-harness"]) == ["langgraph", "agent-harness"]

    def test_invalid_tags_filtered(self):
        assert _normalize_learning_tags(["langgraph", "invalid"]) == ["langgraph"]

    def test_empty_returns_empty(self):
        assert _normalize_learning_tags([]) == []

    def test_non_list_returns_empty(self):
        assert _normalize_learning_tags(None) == []


class TestNormalizeReadingPriority:
    @pytest.mark.parametrize("value,expected", [
        ("study-now", "study-now"),
        ("save-for-context", "save-for-context"),
        ("skim", "skim"),
        ("low-priority", "low-priority"),
        ("skip", "skip"),
        ("invalid", "low-priority"),
        ("", "low-priority"),
        (None, "low-priority"),
    ])
    def test_priority_normalization(self, value, expected):
        assert _normalize_reading_priority(value) == expected


class TestNormalizeSourceType:
    @pytest.mark.parametrize("value,expected", [
        ("repository", "repository"),
        ("paper", "paper"),
        ("blog", "blog"),
        ("invalid", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ])
    def test_source_type_normalization(self, value, expected):
        assert _normalize_source_type(value) == expected


class TestNormalizeLearningTrack:
    @pytest.mark.parametrize("value,expected", [
        ("agent-systems", "agent-systems"),
        ("langgraph-workflows", "langgraph-workflows"),
        ("invalid", "background"),
        ("", "background"),
        (None, "background"),
    ])
    def test_track_normalization(self, value, expected):
        assert _normalize_learning_track(value) == expected


class TestNormalizeSuggestedAction:
    @pytest.mark.parametrize("value,expected", [
        ("clone-and-study", "clone-and-study"),
        ("deep-read", "deep-read"),
        ("skim", "skim"),
        ("archive", "archive"),
        ("skip", "skip"),
        ("invalid", "skim"),
        ("", "skim"),
        (None, "skim"),
    ])
    def test_action_normalization(self, value, expected):
        assert _normalize_suggested_action(value) == expected


class TestRuleCaps:
    def test_discussion_low_fit_capped_to_low_priority(self):
        result = _apply_rule_caps("study-now", "discussion", 0.3, False)
        assert result == "low-priority"

    def test_discussion_medium_fit_capped_to_skim(self):
        result = _apply_rule_caps("study-now", "discussion", 0.6, False)
        assert result == "skim"

    def test_focus_match_boosted_to_save_for_context(self):
        result = _apply_rule_caps("skim", "repository", 0.7, True)
        assert result == "save-for-context"

    def test_focus_match_not_boosted_below_threshold(self):
        result = _apply_rule_caps("skim", "repository", 0.4, True)
        assert result == "skim"

    def test_repository_normal_priority_unchanged(self):
        result = _apply_rule_caps("study-now", "repository", 0.8, False)
        assert result == "study-now"


class TestCheckFocusMatch:
    def test_matches_p0_topic(self):
        profile = {"focus_topics": {"p0_must_learn": ["langgraph", "agent engineering"]}}
        assert _check_focus_match("LangGraph tutorial", "", profile) is True

    def test_no_match(self):
        assert _check_focus_match("random cooking blog", "", DEFAULT_PROFILE) is False


class TestFallbackAnalysis:
    def test_includes_personal_relevance_fields(self):
        item = {"title": "Test", "source": "github", "source_url": "https://example.com", "raw_description": "desc"}
        result = _fallback_analysis(item, RuntimeError("test"))
        assert result["personal_fit_score"] == 0.0
        assert result["reading_priority"] == "low-priority"
        assert result["source_type"] == "unknown"
        assert result["learning_track"] == "background"
        assert result["learning_tags"] == []
        assert result["relevance_reason"] != ""


class TestAnalyzeItem:
    def test_normalizes_all_new_fields(self, mocker):
        mocker.patch(
            "workflows.analyzer.chat_json_with_model",
            return_value=(
                {
                    "summary": "这是一段足够长的中文技术摘要，描述 LangGraph 工作流和 Agent 架构。",
                    "tags": ["llm", "agent"],
                    "relevance_score": 0.9,
                    "category": "agent",
                    "key_insight": "工作流闭环。",
                    "score": 8,
                    "audience": "advanced",
                    "personal_fit_score": 1.5,
                    "technical_depth_score": -0.1,
                    "actionability_score": 0.8,
                    "source_credibility_score": 0.9,
                    "novelty_score": 0.7,
                    "priority_score": 150,
                    "reading_priority": "study-now",
                    "relevance_reason": "直接匹配 P0 Agent 主题",
                    "suggested_action": "clone-and-study",
                    "confidence": 1.2,
                    "source_type": "repository",
                    "learning_track": "agent-systems",
                    "learning_tags": ["langgraph", "agent-harness"],
                },
                MagicMock(prompt_tokens=10, completion_tokens=5),
                "qwen-plus",
            ),
        )

        item = {"title": "LangGraph Repo", "source": "github", "source_url": "https://example.com", "raw_description": "langgraph agent"}
        result, _, _ = analyze_item(item)

        assert result["personal_fit_score"] == 1.0
        assert result["technical_depth_score"] == 0.0
        assert result["actionability_score"] == 0.8
        assert result["priority_score"] == 100
        assert result["reading_priority"] == "study-now"
        assert result["relevance_score"] == 1.0
        assert result["confidence"] == 1.0
        assert result["source_type"] == "repository"
        assert result["learning_track"] == "agent-systems"
        assert result["learning_tags"] == ["langgraph", "agent-harness"]

    def test_uses_active_profile_in_prompt(self, mocker):
        mock_llm = mocker.patch(
            "workflows.analyzer.chat_json_with_model",
            return_value=(
                {
                    "summary": "测试摘要",
                    "tags": ["llm"],
                    "relevance_score": 0.5,
                    "category": "other",
                    "key_insight": "",
                    "score": 5,
                    "audience": "intermediate",
                    "personal_fit_score": 0.5,
                    "technical_depth_score": 0.5,
                    "actionability_score": 0.5,
                    "source_credibility_score": 0.5,
                    "novelty_score": 0.5,
                    "priority_score": 50,
                    "reading_priority": "skim",
                    "relevance_reason": "测试",
                    "suggested_action": "skim",
                    "confidence": 0.5,
                    "source_type": "blog",
                    "learning_track": "background",
                    "learning_tags": [],
                },
                MagicMock(prompt_tokens=10, completion_tokens=5),
                "qwen-plus",
            ),
        )

        custom_profile = dict(DEFAULT_PROFILE)
        custom_profile["user_status"] = "custom test user"
        item = {"title": "Test", "source": "github", "source_url": "https://example.com", "raw_description": "desc"}
        analyze_item(item, profile=custom_profile)

        call_args = mock_llm.call_args
        prompt_text = call_args[0][0] if call_args[0] else ""
        assert "custom test user" in prompt_text
