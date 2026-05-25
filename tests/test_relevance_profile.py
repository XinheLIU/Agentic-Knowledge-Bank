"""Tests for workflows/relevance_profile.py"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from workflows.relevance_profile import (
    DEFAULT_PROFILE,
    VALID_LEARNING_TRACKS,
    VALID_READING_PRIORITIES,
    VALID_SOURCE_TYPES,
    VALID_SUGGESTED_ACTIONS,
    load_relevance_profile,
    profile_summary_text,
)

pytestmark = pytest.mark.non_llm


class TestLoadProfile:
    def test_loads_default_yaml(self):
        profile = load_relevance_profile()
        assert profile["profile_id"] == "default"
        assert "p0_must_learn" in profile["focus_topics"]
        assert len(profile["learning_tracks"]) > 0

    def test_loads_from_custom_path(self, tmp_path):
        custom = tmp_path / "custom.yaml"
        custom.write_text(yaml.safe_dump({
            "profile_id": "custom-test",
            "user_status": "test user",
        }), encoding="utf-8")
        profile = load_relevance_profile(custom)
        assert profile["profile_id"] == "custom-test"
        assert profile["user_status"] == "test user"
        assert "p0_must_learn" in profile["focus_topics"]

    def test_falls_back_to_builtin_default_on_missing_file(self, tmp_path):
        profile = load_relevance_profile(tmp_path / "nonexistent.yaml")
        assert profile["profile_id"] == "builtin-default"

    def test_falls_back_on_invalid_yaml(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": invalid : yaml : [", encoding="utf-8")
        profile = load_relevance_profile(bad)
        assert profile["profile_id"] == "builtin-default"

    def test_partial_config_merges_with_defaults(self, tmp_path):
        partial = tmp_path / "partial.yaml"
        partial.write_text(yaml.safe_dump({
            "user_status": "partial override",
            "focus_topics": {
                "p0_must_learn": ["custom-topic"],
            },
        }), encoding="utf-8")
        profile = load_relevance_profile(partial)
        assert profile["user_status"] == "partial override"
        assert profile["focus_topics"]["p0_must_learn"] == ["custom-topic"]
        assert "p1_valuable_context" in profile["focus_topics"]
        assert len(profile["learning_tracks"]) > 0

    def test_default_profile_has_required_keys(self):
        required_keys = [
            "profile_id", "user_status", "focus_topics",
            "learning_tracks", "preferred_source_types",
            "learning_tag_allowlist", "negative_patterns",
        ]
        for key in required_keys:
            assert key in DEFAULT_PROFILE, f"DEFAULT_PROFILE missing key: {key}"

    def test_default_yaml_file_matches_defaults(self):
        profile = load_relevance_profile()
        for key in DEFAULT_PROFILE:
            assert key in profile


class TestProfileSummaryText:
    def test_generates_non_empty_text(self):
        text = profile_summary_text(DEFAULT_PROFILE)
        assert len(text) > 0
        assert "用户状态" in text
        assert "P0 必学" in text

    def test_handles_empty_profile(self):
        text = profile_summary_text({})
        assert isinstance(text, str)


class TestValidConstants:
    def test_reading_priorities(self):
        assert VALID_READING_PRIORITIES == {"study-now", "save-for-context", "skim", "low-priority", "skip"}

    def test_source_types(self):
        assert "repository" in VALID_SOURCE_TYPES
        assert "unknown" in VALID_SOURCE_TYPES

    def test_learning_tracks(self):
        assert "agent-systems" in VALID_LEARNING_TRACKS
        assert "background" in VALID_LEARNING_TRACKS

    def test_suggested_actions(self):
        assert "clone-and-study" in VALID_SUGGESTED_ACTIONS
        assert "skip" in VALID_SUGGESTED_ACTIONS
