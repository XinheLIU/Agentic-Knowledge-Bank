"""Canonical hollow-word lists (policy §4).

These exact strings are the only surviving artifact of the legacy 115-point
quality rubric; the §2.3 hype detector re-uses them; sole owner of the
vocabulary since the ticket-16 legacy retirement. Keep the lists byte-
identical to the policy document.
"""

from __future__ import annotations

__all__ = [
    "HOLLOW_WORDS_ZH",
    "HOLLOW_WORDS_EN",
    "HOLLOW_WORDS",
    "MECHANISM_KEYWORDS",
]

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

#: Mechanism signal words (policy §2.3): presence in the text exempts an item
#: from the hype and generic-enterprise detectors.
MECHANISM_KEYWORDS = (
    "benchmark", "评测", "ablation", "architecture", "架构", "open-source",
    "github.com", "paper", "论文", "API", "schema", "eval",
)
