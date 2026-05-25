#!/usr/bin/env python3
"""
Quality scoring script for knowledge-base articles.

Six dimensions with a total score of 115:
  1. Summary quality: 25
  2. Technical depth: 25
  3. Format completeness: 20
  4. Tag precision: 15
  5. Hollow-word detection: 15
  6. Personal relevance: 15

Grades: A (>=90), B (>=70), C (<70)

Usage:
    python hooks/check_quality.py knowledge/articles/github-20260317-001.json
    python hooks/check_quality.py knowledge/articles/*.json

Exit codes:
    0: all files are grade B or above
    1: at least one file is grade C
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOLLOW_WORDS_ZH = [
    "赋能", "抓手", "闭环", "打通", "全链路", "底层逻辑",
    "颗粒度", "对齐", "拉通", "沉淀", "强大的", "革命性的",
]

HOLLOW_WORDS_EN = [
    "groundbreaking", "revolutionary", "game-changing", "cutting-edge",
    "state-of-the-art", "leverage", "synergy", "paradigm shift",
    "disruptive", "next-generation", "world-class",
]

HOLLOW_WORDS = HOLLOW_WORDS_ZH + HOLLOW_WORDS_EN

VALID_TAGS = {
    "agent", "rag", "mcp", "llm", "fine-tuning", "prompt-engineering",
    "multi-agent", "tool-use", "evaluation", "deployment", "security",
    "reasoning", "code-generation", "vision", "audio", "robotics",
}

VALID_LEARNING_TAGS = {
    "agent-harness", "langgraph", "langchain", "data-agent", "mcp",
    "tool-use", "browser-agent", "computer-use", "evaluation",
    "repo-tutorial", "reference-architecture", "paper-to-code",
    "production-rag", "local-llm", "quant-ai", "business-context",
    "implementation-pattern", "architecture-reference", "production-lesson",
    "research-method", "noise",
}


@dataclass
class DimensionScore:
    """Score for one quality dimension."""
    name: str
    score: float
    max_score: float
    details: str

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


@dataclass
class QualityReport:
    """Quality evaluation report."""
    filepath: str
    dimensions: list[DimensionScore]

    @property
    def total_score(self) -> float:
        return sum(d.score for d in self.dimensions)

    @property
    def max_total(self) -> float:
        return sum(d.max_score for d in self.dimensions)

    @property
    def grade(self) -> str:
        score = self.total_score
        if score >= 90:
            return "A"
        elif score >= 70:
            return "B"
        else:
            return "C"


def score_summary_quality(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 1: summary quality (25 points).

    Scoring rules:
    - Summary length >= 50 chars: 20 points
    - Summary length >= 20 chars: 15 points
    - Short summary: 5 points
    - Missing summary: 0 points
    - Technical keyword bonus: up to 5 points
    """
    max_score = 25.0
    summary = data.get("summary", "").strip()

    if not summary:
        return DimensionScore("摘要质量", 0, max_score, "无摘要")

    length = len(summary)
    if length >= 50:
        base = 20.0
        detail = f"长度充足 ({length} 字)"
    elif length >= 20:
        base = 15.0
        detail = f"长度基本 ({length} 字)"
    else:
        base = 5.0
        detail = f"太短 ({length} 字)"

    tech_keywords = [
        "模型", "训练", "推理", "API", "框架", "agent", "LLM", "RAG",
        "token", "向量", "embedding", "transformer", "微调",
        "model", "training", "inference", "framework",
    ]
    keyword_count = sum(1 for kw in tech_keywords if kw.lower() in summary.lower())
    bonus = min(5.0, keyword_count * 1.0)
    if bonus > 0:
        detail += f", 含 {keyword_count} 个技术关键词"

    score = min(max_score, base + bonus)
    return DimensionScore("摘要质量", score, max_score, detail)


def score_tech_depth(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 2: technical depth (25 points).

    Uses personal_fit_score and technical_depth_score when available,
    falls back to article score field.
    """
    max_score = 25.0

    personal_fit = data.get("personal_fit_score")
    tech_depth = data.get("technical_depth_score")

    if isinstance(personal_fit, (int, float)) and isinstance(tech_depth, (int, float)):
        combined = (float(personal_fit) * 0.4 + float(tech_depth) * 0.6)
        mapped = combined * max_score
        detail = f"个人匹配 {personal_fit:.2f} + 技术深度 {tech_depth:.2f} → {mapped:.1f}/{max_score}"
        return DimensionScore("技术深度", round(mapped, 1), max_score, detail)

    article_score = data.get("score", 5)
    if not isinstance(article_score, (int, float)):
        return DimensionScore("技术深度", 10, max_score, "score 字段类型异常")

    mapped = (article_score / 10) * max_score
    detail = f"文章评分 {article_score}/10 → {mapped:.1f}/{max_score}"

    return DimensionScore("技术深度", round(mapped, 1), max_score, detail)


def score_format(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 3: format completeness (20 points).

    Checks:
    - id (+4)
    - title (+4)
    - source_url (+4)
    - status (+4)
    - updated_at or collected_at (+4)
    """
    max_score = 20.0
    score = 0.0
    checks: list[str] = []

    field_checks = [
        ("id", 4),
        ("title", 4),
        ("source_url", 4),
        ("status", 4),
    ]

    for field_name, points in field_checks:
        val = data.get(field_name, "")
        if val and str(val).strip():
            score += points
        else:
            checks.append(f"缺少 {field_name}")

    if data.get("updated_at") or data.get("collected_at"):
        score += 4
    else:
        checks.append("缺少时间戳")

    detail = "完整" if not checks else "缺失: " + ", ".join(checks)
    return DimensionScore("格式规范", score, max_score, detail)


def score_tags(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 4: tag precision (15 points).

    Scoring rules:
    - Broad tags (1-3 valid): up to 8 points
    - Learning tags present: up to 7 points
    - Too many broad tags (>5): penalty
    - No tags at all: 0 points
    """
    max_score = 15.0
    tags = data.get("tags", [])
    learning_tags = data.get("learning_tags", [])

    if not tags and not learning_tags:
        return DimensionScore("标签精度", 0, max_score, "无标签")

    broad_valid = sum(1 for t in tags if t in VALID_TAGS)
    broad_total = len(tags)

    if 1 <= broad_total <= 3 and broad_valid == broad_total:
        broad_score = 8.0
        broad_detail = f"{broad_total} 个标签，全部合法"
    elif broad_valid > 0:
        broad_score = 5.0
        broad_detail = f"{broad_valid}/{broad_total} 个合法标签"
    else:
        broad_score = 0.0
        broad_detail = "无合法宽标签"

    if broad_total > 5:
        penalty = min(3.0, (broad_total - 5) * 1.0)
        broad_score = max(0, broad_score - penalty)
        broad_detail += f", 标签过多 (扣 {penalty} 分)"

    learning_valid = sum(1 for t in learning_tags if t in VALID_LEARNING_TAGS)
    if learning_valid > 0:
        learning_score = min(7.0, learning_valid * 2.5)
        learning_detail = f"{learning_valid} 个学习标签"
    else:
        learning_score = 0.0
        learning_detail = "无学习标签"

    score = min(max_score, broad_score + learning_score)
    detail = f"{broad_detail}; {learning_detail}"

    return DimensionScore("标签精度", score, max_score, detail)


def score_hollow_words(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 5: hollow-word detection (15 points).

    Each hollow word in the title or summary costs 3 points.
    """
    max_score = 15.0
    text = (data.get("summary", "") + " " + data.get("title", "")).lower()

    found: list[str] = []
    for word in HOLLOW_WORDS:
        if word.lower() in text:
            found.append(word)

    penalty = min(max_score, len(found) * 3.0)
    score = max_score - penalty

    if found:
        detail = f"发现 {len(found)} 个空洞词: {', '.join(found[:5])}"
    else:
        detail = "未发现空洞词"

    return DimensionScore("空洞词检测", score, max_score, detail)


def score_personal_relevance(data: dict[str, Any]) -> DimensionScore:
    """
    Dimension 6: personal relevance (15 points).

    Rewards articles that include personal intelligence fields:
    - reading_priority present and valid: +3
    - relevance_reason non-empty: +3
    - suggested_action present and valid: +2
    - source_type present and valid: +2
    - learning_track present and valid: +2
    - personal_fit_score in valid range: +3
    """
    max_score = 15.0
    score = 0.0
    checks: list[str] = []

    valid_priorities = {"study-now", "save-for-context", "skim", "low-priority", "skip"}
    valid_source_types = {
        "repository", "paper", "blog", "discussion", "benchmark",
        "tutorial", "product", "news", "documentation", "unknown",
    }
    valid_tracks = {
        "agent-systems", "langgraph-workflows", "data-agents",
        "rag-knowledge-systems", "evaluation", "local-model-serving",
        "ml-rl-foundations", "quant-data-science", "engineering-leadership",
        "business-context", "background",
    }
    valid_actions = {"clone-and-study", "deep-read", "skim", "archive", "skip"}

    rp = data.get("reading_priority")
    if rp and rp in valid_priorities:
        score += 3
    else:
        checks.append("缺少 reading_priority")

    rr = data.get("relevance_reason")
    if rr and str(rr).strip():
        score += 3
    else:
        checks.append("缺少 relevance_reason")

    sa = data.get("suggested_action")
    if sa and sa in valid_actions:
        score += 2
    else:
        checks.append("缺少 suggested_action")

    st = data.get("source_type")
    if st and st in valid_source_types:
        score += 2
    else:
        checks.append("缺少 source_type")

    lt = data.get("learning_track")
    if lt and lt in valid_tracks:
        score += 2
    else:
        checks.append("缺少 learning_track")

    pf = data.get("personal_fit_score")
    if isinstance(pf, (int, float)) and 0.0 <= float(pf) <= 1.0:
        score += 3
    else:
        checks.append("缺少 personal_fit_score")

    detail = "完整" if not checks else "缺失: " + ", ".join(checks)
    return DimensionScore("个人相关性", score, max_score, detail)


def evaluate_quality(filepath: str, data: dict[str, Any]) -> QualityReport:
    """
    Evaluate one article across all five quality dimensions.

    Args:
        filepath: Article file path.
        data: Article JSON data.

    Returns:
        Quality report.
    """
    dimensions = [
        score_summary_quality(data),
        score_tech_depth(data),
        score_format(data),
        score_tags(data),
        score_hollow_words(data),
        score_personal_relevance(data),
    ]

    return QualityReport(filepath=filepath, dimensions=dimensions)


def print_report(report: QualityReport) -> None:
    """Print a formatted quality report."""
    print(f"\n{'─'*50}")
    print(f"文件: {report.filepath}")
    print(f"{'─'*50}")

    for d in report.dimensions:
        bar_len = int(d.percentage / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {d.name:10s} [{bar}] {d.score:5.1f}/{d.max_score:.0f}  {d.details}")

    grade_emoji = {"A": "🟢", "B": "🟡", "C": "🔴"}
    emoji = grade_emoji.get(report.grade, "")
    print(f"\n  总分: {report.total_score:.1f}/{report.max_total:.0f}  "
          f"等级: {emoji} {report.grade}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python hooks/check_quality.py <json_file> [json_file2 ...]")
        print("示例: python hooks/check_quality.py knowledge/articles/*.json")
        return 1

    files = sys.argv[1:]
    total_files = 0
    grade_counts = {"A": 0, "B": 0, "C": 0}
    has_c_grade = False

    for filepath in files:
        path = Path(filepath)
        if not path.exists() or path.suffix != ".json":
            continue

        total_files += 1

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] {filepath}: JSON 解析失败 — {e}")
            has_c_grade = True
            continue

        report = evaluate_quality(filepath, data)
        print_report(report)
        grade_counts[report.grade] = grade_counts.get(report.grade, 0) + 1

        if report.grade == "C":
            has_c_grade = True

    print(f"\n{'='*50}")
    print(f"质量评估汇总: {total_files} 文件")
    print(f"  A 级 (>=80): {grade_counts.get('A', 0)}")
    print(f"  B 级 (>=60): {grade_counts.get('B', 0)}")
    print(f"  C 级 (<60):  {grade_counts.get('C', 0)}")
    print(f"{'='*50}")

    return 1 if has_c_grade else 0


if __name__ == "__main__":
    sys.exit(main())
