"""Deterministic per-item admission function (policy §2, ticket 09, O1).

Pure, I/O-free, per-item: no LLM, no prompt machinery, no store, no batch
score consumer. ``admit()`` evaluates ONE mapped candidate against the
versioned policy and returns an :class:`AdmissionDecision` shaped exactly as
the ``admissions`` ledger row (asset-audit-model §3/§6; ticket 07 persists it,
ticket 10 feeds it).

Phase order is normative (policy §2.1): dedup → integrity → noise → score
gate, short-circuiting at the first terminal rule. Warnings never change an
outcome; they are appended to the final row's ``reason_codes``.

Reason-code *membership* is owned by the shared ``kb/model.py`` registry; this
module owns only semantics (thresholds, order, evidence shape).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from kb.admission.patterns import PATTERN_SPECS, PatternSpec, match_patterns
from kb.model import normalize_url

__all__ = [
    "POLICY_ID",
    "POLICY_VERSION",
    "AdmissionDecision",
    "AdmissionPolicy",
    "DedupState",
    "admit",
    "classify_topics",
    "source_class_of",
]

POLICY_ID = "admission-policy"
POLICY_VERSION = "0.1.0"

# Verbatim topic lists (policy §1.4).
P0_TOPICS: tuple[str, ...] = (
    "agent engineering", "langgraph", "langchain", "tool-use", "mcp",
    "browser agents", "computer-use agents", "data agents",
    "rag knowledge systems", "production evaluation",
)
P1_TOPICS: tuple[str, ...] = (
    "llm engineering", "ai coding systems", "local model workflows",
    "applied ml", "reinforcement learning", "quantitative analysis",
    "data science methodology", "engineering architecture",
)
P2_TOPICS: tuple[str, ...] = (
    "generic ai discourse", "business context", "technical communication",
)

#: Horizon fetch enum / legacy taxonomy → policy source class (policy §1.5).
SOURCE_CLASS_OF_TYPE: dict[str, str] = {
    "github": "repository", "openbb": "repository", "ossinsight": "repository",
    "rss": "blog",
    "hackernews": "discussion", "reddit": "discussion",
    "telegram": "news", "twitter": "news", "gdelt": "news", "google_news": "news",
    # legacy taxonomy fallbacks
    "repository": "repository", "tutorial": "repository",
    "documentation": "repository", "paper": "repository", "benchmark": "repository",
    "blog": "blog", "product": "blog",
    "discussion": "discussion",
    "news": "news",
}

SOURCE_CLASS_BOOSTS: dict[str, float] = {
    "repository": 1.0, "blog": 0.0, "discussion": -0.5, "news": -0.5,
}


def source_class_of(source_type: str | None) -> str:
    """Map a Horizon fetch enum / legacy source type to its policy class."""
    return SOURCE_CLASS_OF_TYPE.get(source_type or "", "blog")


def classify_topics(title: str, summary: str) -> tuple[str, list[str]]:
    """Return ``(topic_tier, matched_topics)`` evidence (policy §1.3/§3).

    Deterministic substring classification over ``title + summary``; tier
    precedence is p0 > p1 > p2 > none. Pure.
    """
    text = f"{title}\n{summary}".lower()
    matched: list[str] = []
    tier = "none"
    for tier_name in ("p0", "p1", "p2"):
        topics = {"p0": P0_TOPICS, "p1": P1_TOPICS, "p2": P2_TOPICS}[tier_name]
        for topic in topics:
            if topic in text:
                matched.append(topic)
                if tier == "none":
                    tier = tier_name
    return tier, matched


@dataclass(frozen=True)
class DedupState:
    """Dedup inputs supplied by the caller (store/run knowledge, policy §2.4).

    The policy stays pure: the caller (ticket 10 ingest) queries the store for
    already-persisted asset ids/URLs and already-decided candidates of the
    current run, then hands them in. Raw URLs are normalized *here* via the
    single owner ``kb.model.normalize_url``.
    """

    #: Asset ids persisted from earlier runs + item ids decided in this run.
    decided_item_ids: tuple[str, ...] = ()
    #: Raw URLs persisted as accepted assets or decided in this run.
    decided_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmissionPolicy:
    """Versioned thresholds and detector constants (policy §2.2/§2.3)."""

    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    base_accept: float = 7.0          # A1 (Horizon tech-news wizard default)
    rescue_accept: float = 6.0        # A2 P0 rescue floor
    low_source_raw_floor: float = 7.0  # A3 raw-score cap for discussion/news
    low_confidence: float = 0.5       # §2.6 warning + A2 eligibility loss
    min_hollow_words: int = 2         # §2.3 hype detector
    shallow_launch_max_score: float = 8.0
    shallow_summary_max_chars: int = 120

    def check(self) -> None:
        """Fail fast on constants inconsistent with the policy doc."""
        if self.rescue_accept >= self.base_accept:
            raise ValueError("rescue floor must be below the base gate")
        if not 0.0 <= self.low_confidence <= 1.0:
            raise ValueError("low_confidence must be within 0.0-1.0")


@dataclass(frozen=True)
class AdmissionDecision:
    """Outcome of one per-item admission (one ``admissions`` ledger row)."""

    item_id: str
    outcome: str                       # accepted | rejected | failed
    reason_codes: tuple[str, ...]      # ordered: terminal codes, warnings last
    evidence: dict[str, Any] = field(default_factory=dict)
    duplicate_of: str | None = None    # ledger column, never inside evidence
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION

    @property
    def accepted(self) -> bool:
        return self.outcome == "accepted"

    def to_row(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "outcome": self.outcome,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "reason_codes": list(self.reason_codes),
            "evidence_json": json.dumps(self.evidence, ensure_ascii=False, sort_keys=True),
            "duplicate_of": self.duplicate_of,
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _malformed_enrichment(item: Mapping[str, Any]) -> bool:
    """Tags non-list / reason non-string / artifacts malformed (policy §2.5)."""
    tags = item.get("tags")
    if tags is not None and not isinstance(tags, list):
        return True
    reason = item.get("score_reason")
    if reason is not None and not isinstance(reason, str):
        return True
    artifacts = item.get("artifacts")
    if artifacts is not None and not isinstance(artifacts, list):
        return True
    return False


def _malformed_metadata(item: Mapping[str, Any]) -> bool:
    """Metadata not JSON-serializable (policy §2.5) → coerced, warned."""
    metadata = item.get("metadata_json")
    if metadata is None:
        return False
    try:
        json.dumps(metadata, ensure_ascii=False)
    except (TypeError, ValueError):
        return True
    return False


def _low_confidence(item: Mapping[str, Any], policy: AdmissionPolicy) -> bool:
    """§2.6: missing/low confidence on a model-routed item (never source_override)."""
    method = item.get("profile_method")
    if method == "source_override":
        return False
    confidence = item.get("profile_confidence")
    return confidence is None or not _is_number(confidence) or confidence < policy.low_confidence


def admit(
    item: Mapping[str, Any],
    policy: AdmissionPolicy,
    *,
    dedup: DedupState = DedupState(),
) -> AdmissionDecision:
    """Admit one mapped candidate; pure, per-item (O1), prompt-free (O3).

    ``item`` is a mapped store-input dict (``kb.horizon.mapper.map_content_item``
    vocabulary). Evaluation order is normative; the first terminal rule ends
    evaluation. All reason codes come from the ``kb/model.py`` registry.
    """
    policy.check()
    item_id = str(item.get("id") or "")
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    url = str(item.get("url") or "")
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    score = item.get("score")
    source_class = source_class_of(item.get("source_type"))
    boost = SOURCE_CLASS_BOOSTS[source_class]
    topic_tier, matched_topics = classify_topics(title, summary)
    pattern: str | None = None

    def decision(
        outcome: str, terminal: list[str], duplicate_of: str | None = None
    ) -> AdmissionDecision:
        return AdmissionDecision(
            item_id=item_id,
            outcome=outcome,
            reason_codes=tuple(terminal) + tuple(warnings),
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            evidence={
                "checks": checks,
                "raw_score": score if _is_number(score) else None,
                "effective_score": (score + boost) if _is_number(score) else None,
                "boost": boost,
                "topic_tier": topic_tier,
                "matched_topics": matched_topics,
                "source_class": source_class,
                "confidence": item.get("profile_confidence"),
                "warnings": list(warnings),
                "pattern": pattern,
                "summary_len": len(summary),
                "tags": list(item.get("tags") or []) if isinstance(item.get("tags"), list) else [],
            },
            duplicate_of=duplicate_of,
        )

    # --- Phase 0: dedup (exact match with asset-audit-model §1.2) -----------
    if item_id and item_id in dedup.decided_item_ids:
        checks.append({"phase": "dedup", "rule": "id", "hit": True})
        return decision("rejected", ["DUPLICATE_ID"], duplicate_of=item_id)
    checks.append({"phase": "dedup", "rule": "id", "hit": False})
    normalized = normalize_url(url) if url else ""
    for existing in dedup.decided_urls:
        if normalized and normalize_url(existing) == normalized:
            checks.append({"phase": "dedup", "rule": "url", "hit": True})
            return decision("rejected", ["DUPLICATE_URL"], duplicate_of=existing)
    checks.append({"phase": "dedup", "rule": "url", "hit": False})

    # --- Warnings (parallel channel; never terminal) ------------------------
    if _malformed_enrichment(item):
        warnings.append("MALFORMED_ENRICHMENT")
    if _malformed_metadata(item):
        warnings.append("MALFORMED_METADATA")
    low_conf = _low_confidence(item, policy)
    if low_conf:
        warnings.append("LOW_CONFIDENCE_MATCH")

    # --- Phase 1: integrity (degraded behavior, policy §2.5) ----------------
    if not _is_number(score):
        checks.append({"phase": "integrity", "rule": "missing_score", "hit": True})
        return decision("rejected", ["MISSING_SCORE"])
    checks.append({"phase": "integrity", "rule": "missing_score", "hit": False})
    if not summary.strip():
        checks.append({"phase": "integrity", "rule": "missing_summary", "hit": True})
        return decision("rejected", ["MISSING_SUMMARY"])
    checks.append({"phase": "integrity", "rule": "missing_summary", "hit": False})
    if not str(item.get("published_at") or "").strip():
        checks.append({"phase": "integrity", "rule": "missing_published_at", "hit": True})
        return decision("rejected", ["MISSING_PUBLISHED_AT"])
    checks.append({"phase": "integrity", "rule": "missing_published_at", "hit": False})

    # --- Phase 2: noise (executable negative patterns, O3) ------------------
    ctx = {"title": title, "summary": summary, "score": score, "topic_tier": topic_tier}
    spec: PatternSpec | None = match_patterns(ctx)
    for candidate in PATTERN_SPECS:
        checks.append({
            "phase": "noise",
            "rule": candidate.rule,
            "hit": spec is not None and candidate.label == spec.label,
        })
    if spec is not None:
        pattern = spec.label
        return decision("rejected", [spec.reason_code])

    # --- Phase 3: score gate (A3 → A2 → A1 → A4) ----------------------------
    effective = float(score) + boost
    a3 = source_class in ("discussion", "news") and float(score) < policy.low_source_raw_floor
    checks.append({"phase": "score_gate", "rule": "a3_low_source_cap", "hit": a3})
    if a3:
        return decision("rejected", ["REJECTED_LOW_SCORE", "LOW_SOURCE_TYPE"])
    a2 = (
        policy.rescue_accept <= effective < policy.base_accept
        and topic_tier == "p0"
        and not low_conf  # low confidence loses A2 rescue eligibility (§2.6)
    )
    # Rescue is bounded below the base gate: a P0 item already passing A1 takes
    # the A1 path ("ACCEPTED" ± "TOPIC_P0_BOOST") — that documented A1 variant
    # is otherwise unreachable, and "rescued" would mislabel a clean accept.
    checks.append({"phase": "score_gate", "rule": "a2_rescue", "hit": a2})
    if a2:
        return decision(
            "accepted", ["ACCEPTED", "TOPIC_P0_BOOST", "RESCUED_BY_TOPIC"]
        )
    a1 = effective >= policy.base_accept
    checks.append({"phase": "score_gate", "rule": "a1_base", "hit": a1})
    if a1:
        terminal = ["ACCEPTED"] + (["TOPIC_P0_BOOST"] if topic_tier == "p0" else [])
        return decision("accepted", terminal)
    checks.append({"phase": "score_gate", "rule": "a4_reject", "hit": True})
    return decision("rejected", ["REJECTED_LOW_SCORE"])
