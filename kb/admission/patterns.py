"""Typed negative-pattern detector specs (policy §2.3, O3).

Data, not prompts: each legacy ``relevance_profile.yaml`` label maps to one
deterministic spec. The first matching spec (in :data:`PATTERN_SPECS` order)
rejects the item in admission phase 2; the matched legacy **label** is
recorded in ``evidence_json.pattern``. Adding a pattern means adding a spec —
never prompt text. This module imports no LLM/prompt machinery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Final

from kb.admission.hollow_words import HOLLOW_WORDS, MECHANISM_KEYWORDS
from kb.model import ReasonCode

__all__ = ["PatternSpec", "PATTERN_SPECS", "match_patterns"]


@dataclass(frozen=True)
class PatternSpec:
    """One executable negative-pattern detector (policy §2.3 table row)."""

    #: Legacy label, verbatim from ``relevance_profile.yaml``; recorded in
    #: ``evidence_json.pattern`` when the spec hits.
    label: str
    #: Registered reason code from the shared ``kb/model.py`` registry.
    reason_code: str
    #: Stable rule name used in ``evidence_json.checks[].rule``.
    rule: str
    #: Pure predicate over the evaluation context; returns True on a hit.
    detect: Callable[[dict[str, Any]], bool]


def _has_mechanism(text: str) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in MECHANISM_KEYWORDS)


def _hype_no_mechanism(ctx: dict[str, Any]) -> bool:
    text = f"{ctx['title']}\n{ctx['summary']}".lower()
    if _has_mechanism(text):
        return False
    hits = sum(1 for word in HOLLOW_WORDS if word.lower() in text)
    return hits >= 2


_HIRING_RE: Final = re.compile(
    r"(hiring|we're hiring|join our team|招聘|call for (papers|speakers)|cfp"
    r"|registration (is|now) open)",
    re.IGNORECASE,
)


def _hiring_conference(ctx: dict[str, Any]) -> bool:
    return _HIRING_RE.search(ctx["title"]) is not None


_LAUNCH_RE: Final = re.compile(
    r"(launch(?:es|ed)?|releases?|announces?|now available|raising|series [a-c])",
    re.IGNORECASE,
)


def _shallow_launch(ctx: dict[str, Any]) -> bool:
    return (
        _LAUNCH_RE.search(ctx["title"]) is not None
        and ctx["score"] is not None
        and ctx["score"] < 8.0
        and len(ctx["summary"]) < 120
    )


_ENTERPRISE_WORDS: Final = (
    "enterprise", "transform", "digital", "strategy", "行业", "企业", "战略", "赋能",
)


def _generic_enterprise(ctx: dict[str, Any]) -> bool:
    if ctx["topic_tier"] == "p0":
        return False
    if _has_mechanism(ctx["summary"]):
        return False
    hits = sum(1 for word in _ENTERPRISE_WORDS if word in ctx["summary"].lower())
    return hits >= 2


def _check_code(code: str) -> str:
    if not ReasonCode.is_registered(code):
        raise ValueError(f"reason code {code!r} is not in the kb/model.py registry")
    return code


PATTERN_SPECS: Final[tuple[PatternSpec, ...]] = (
    PatternSpec(
        label="hype without technical mechanism",
        reason_code=_check_code("NEG_HYPE_NO_MECHANISM"),
        rule="hype_without_technical_mechanism",
        detect=_hype_no_mechanism,
    ),
    PatternSpec(
        label="hiring or conference administration",
        reason_code=_check_code("NEG_HIRING_CONFERENCE"),
        rule="hiring_or_conference_administration",
        detect=_hiring_conference,
    ),
    PatternSpec(
        label="shallow product launch",
        reason_code=_check_code("NEG_SHALLOW_LAUNCH"),
        rule="shallow_product_launch",
        detect=_shallow_launch,
    ),
    PatternSpec(
        label="generic enterprise AI commentary",
        reason_code=_check_code("NEG_GENERIC_ENTERPRISE"),
        rule="generic_enterprise_ai_commentary",
        detect=_generic_enterprise,
    ),
)


def match_patterns(ctx: dict[str, Any]) -> PatternSpec | None:
    """Return the first matching spec (policy order), or ``None``.

    Pure; evaluation order is the :data:`PATTERN_SPECS` tuple order.
    """
    for spec in PATTERN_SPECS:
        if spec.detect(ctx):
            return spec
    return None
