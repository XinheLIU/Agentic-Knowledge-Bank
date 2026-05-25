"""Relevance profile loader: reads user-editable YAML config with safe defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "workflows" / "relevance_profile.yaml"

DEFAULT_PROFILE: dict[str, Any] = {
    "profile_id": "builtin-default",
    "user_status": "AI/LLM/Agent learner",
    "focus_topics": {
        "p0_must_learn": ["agent engineering", "llm"],
        "p1_valuable_context": ["applied ml", "engineering architecture"],
        "p2_background": ["generic ai discourse"],
    },
    "learning_tracks": [
        "agent-systems", "langgraph-workflows", "data-agents",
        "rag-knowledge-systems", "evaluation", "local-model-serving",
        "ml-rl-foundations", "quant-data-science", "engineering-leadership",
    ],
    "preferred_source_types": {
        "high": ["repository", "tutorial", "documentation", "paper", "benchmark"],
        "medium": ["blog", "product"],
        "low": ["discussion", "news"],
    },
    "learning_tag_allowlist": [
        "agent-harness", "langgraph", "langchain", "data-agent", "mcp",
        "tool-use", "browser-agent", "computer-use", "evaluation",
        "repo-tutorial", "reference-architecture", "paper-to-code",
        "production-rag", "local-llm", "quant-ai", "business-context",
        "implementation-pattern", "architecture-reference", "production-lesson",
        "research-method", "noise",
    ],
    "negative_patterns": [
        "hype without technical mechanism",
        "hiring or conference administration",
        "shallow product launch",
        "generic enterprise AI commentary",
    ],
}

VALID_READING_PRIORITIES = {"study-now", "save-for-context", "skim", "low-priority", "skip"}

VALID_SOURCE_TYPES = {
    "repository", "paper", "blog", "discussion", "benchmark",
    "tutorial", "product", "news", "documentation", "unknown",
}

VALID_LEARNING_TRACKS = {
    "agent-systems", "langgraph-workflows", "data-agents",
    "rag-knowledge-systems", "evaluation", "local-model-serving",
    "ml-rl-foundations", "quant-data-science", "engineering-leadership",
    "business-context", "background",
}

VALID_SUGGESTED_ACTIONS = {
    "clone-and-study", "deep-read", "skim", "archive", "skip",
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_relevance_profile(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or DEFAULT_PROFILE_PATH

    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                return _deep_merge(DEFAULT_PROFILE, loaded)
        except (yaml.YAMLError, OSError):
            pass

    return dict(DEFAULT_PROFILE)


def profile_summary_text(profile: dict[str, Any]) -> str:
    lines: list[str] = []

    status = profile.get("user_status", "")
    if status:
        lines.append(f"用户状态: {status}")

    focus = profile.get("focus_topics", {})
    for tier_name, label in [
        ("p0_must_learn", "P0 必学"),
        ("p1_valuable_context", "P1 有价值上下文"),
        ("p2_background", "P2 背景"),
    ]:
        topics = focus.get(tier_name, [])
        if topics:
            lines.append(f"{label}: {', '.join(topics)}")

    tracks = profile.get("learning_tracks", [])
    if tracks:
        lines.append(f"学习路线: {', '.join(tracks)}")

    src_prefs = profile.get("preferred_source_types", {})
    for tier_name, label in [("high", "高价值来源"), ("medium", "中等来源"), ("low", "低价值来源")]:
        sources = src_prefs.get(tier_name, [])
        if sources:
            lines.append(f"{label}: {', '.join(sources)}")

    neg = profile.get("negative_patterns", [])
    if neg:
        lines.append(f"噪音模式: {', '.join(neg)}")

    return "\n".join(lines)
