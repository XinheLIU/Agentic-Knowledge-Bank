"""Ticket 09 tests — deterministic per-item admission (O1, O3).

No LLM, no network, no store: ``admit()`` is exercised as a pure function.
Coverage: per-item independence (O1), prompt-free negative-pattern rejection
(O3), integrity/degraded behavior, duplicates, low confidence, replay
invariant, and evidence/reason-code ordering.
"""

from __future__ import annotations

import json

import pytest

from kb.admission import (
    POLICY_ID,
    POLICY_VERSION,
    AdmissionPolicy,
    DedupState,
    admit,
)
from kb.admission.hollow_words import HOLLOW_WORDS, HOLLOW_WORDS_EN, HOLLOW_WORDS_ZH
from kb.admission.patterns import PATTERN_SPECS
from kb.model import ReasonCode

pytestmark = pytest.mark.non_llm


def make_item(**overrides):
    base = {
        "id": "horizon:abc-123",
        "title": "A LangGraph workflow for production evaluation",
        "url": "https://example.com/posts/langgraph-eval",
        "published_at": "2026-09-12T00:00:00Z",
        "source_type": "github",
        "summary": (
            "Builds an evaluation harness with benchmarks, ablations, and an "
            "open-source architecture; covers scoring, regression gates, and "
            "CI integration for agent workflows."
        ),
        "score": 8.0,
        "score_reason": "concrete mechanism",
        "tags": ["langgraph", "evaluation"],
        "artifacts": [],
        "metadata_json": {"lang": "en"},
        "profile": "ai-kb-personal",
        "profile_method": "ai_match",
        "profile_confidence": 0.9,
        "profile_reason": "matched profile",
    }
    base.update(overrides)
    return base


def base_policy() -> AdmissionPolicy:
    return AdmissionPolicy()


def neutral_item(**overrides):
    """An item whose title/summary match NO focus topic (tier=none)."""
    return make_item(
        title="Quarterly platform notes",
        summary="Routine maintenance notes and minor updates about a desktop utility.",
        **overrides,
    )


# ---------------------------------------------------------------------------
# Policy constants and registry membership (O2: shared vocabulary)
# ---------------------------------------------------------------------------


def test_policy_identity_matches_doc():
    policy = base_policy()
    assert policy.policy_id == POLICY_ID == "admission-policy"
    assert policy.policy_version == POLICY_VERSION == "0.1.0"


def test_all_admission_codes_are_registered():
    policy = base_policy()
    for decision in _every_outcome(policy):
        for code in decision.reason_codes:
            assert ReasonCode.is_registered(code), code


def _every_outcome(policy):
    yield admit(make_item(), policy)
    yield admit(make_item(score=None), policy)
    yield admit(make_item(summary="  "), policy)
    yield admit(make_item(published_at=None), policy)
    yield admit(make_item(source_type="hackernews", score=6.5), policy)
    yield admit(make_item(score=5.0), policy)
    yield admit(make_item(title="We're hiring!"), policy)
    yield admit(make_item(), policy, dedup=DedupState(("horizon:abc-123", ())))


# ---------------------------------------------------------------------------
# O1: per-item independence
# ---------------------------------------------------------------------------


def test_o1_per_item_independence():
    """Changing item k's inputs cannot change item j's decision."""
    policy = base_policy()
    items = [
        make_item(id="horizon:1", score=8.5),
        make_item(id="horizon:2", score=4.0),
        make_item(id="horizon:3", score=None),
    ]
    alone = [admit(item, policy) for item in items]
    together = admit_batch(items, policy)
    for a, b in zip(alone, together):
        assert (a.outcome, a.reason_codes) == (b.outcome, b.reason_codes)


def admit_batch(items, policy):
    """Plain per-item loop — the only batching that exists is iteration."""
    return [admit(item, policy) for item in items]


def test_o1_no_batch_score_consumer():
    """No module in kb/admission consumes a batch-level score sample."""
    import inspect

    import kb.admission
    import kb.admission.patterns as patterns_mod
    import kb.admission.policy as policy_mod

    for mod in (kb.admission, policy_mod, patterns_mod):
        src = inspect.getsource(mod)
        assert "analyses[:5]" not in src
        assert "batch" not in src.replace("batching", "").replace(
            "no batch", ""
        ).replace("batch score consumer", "")


def test_o1_every_scored_candidate_gets_a_record():
    """threshold:null posture: even a raw-0.0 item gets an explicit row."""
    decision = admit(make_item(score=0.0), base_policy())
    assert decision.outcome == "rejected"
    assert "REJECTED_LOW_SCORE" in decision.reason_codes


# ---------------------------------------------------------------------------
# O3: executable negative patterns (prompt-free)
# ---------------------------------------------------------------------------


def test_o3_labels_map_to_typed_specs():
    labels = {spec.label for spec in PATTERN_SPECS}
    assert labels == {
        "hype without technical mechanism",
        "hiring or conference administration",
        "shallow product launch",
        "generic enterprise AI commentary",
    }
    for spec in PATTERN_SPECS:
        assert ReasonCode.is_registered(spec.reason_code)


def test_o3_spec_codes_are_negative_namespace():
    for spec in PATTERN_SPECS:
        assert spec.reason_code.startswith("NEG_")
        assert ReasonCode.namespace_of(spec.reason_code) == "policy_negative_patterns"


@pytest.mark.parametrize(
    ("overrides", "expected_code", "expected_label"),
    [
        (
            {
                "title": "This groundbreaking revolutionary platform changes everything",
                "summary": (
                    "Leverage synergy for a game-changing paradigm shift with "
                    "world-class disruption, no mechanism described."
                ),
            },
            "NEG_HYPE_NO_MECHANISM",
            "hype without technical mechanism",
        ),
        (
            {"title": "We're hiring: join our team of agent researchers"},
            "NEG_HIRING_CONFERENCE",
            "hiring or conference administration",
        ),
        (
            {
                "title": "Acme launches new agent dashboard, now available",
                "summary": "A short launch note.",
                "score": 7.5,
            },
            "NEG_SHALLOW_LAUNCH",
            "shallow product launch",
        ),
        (
            {
                "title": "Enterprise AI outlook",
                "source_type": "rss",
                "summary": (
                    "Enterprise digital transformation strategy for the modern "
                    "business landscape."
                ),
            },
            "NEG_GENERIC_ENTERPRISE",
            "generic enterprise AI commentary",
        ),
    ],
)
def test_o3_each_pattern_rejects(overrides, expected_code, expected_label):
    policy = base_policy()
    decision = admit(make_item(**overrides), policy)
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == expected_code
    assert decision.evidence["pattern"] == expected_label


def test_o3_hype_with_mechanism_is_not_rejected():
    decision = admit(
        make_item(
            title="A groundbreaking evaluation architecture for LangGraph",
            summary=(
                "Revolutionary ablation benchmark with open-source code at "
                "github.com and a full paper."
            ),
        ),
        base_policy(),
    )
    assert decision.outcome == "accepted"


def test_o3_rejection_with_ai_layer_stubbed():
    """Rejection needs only the mapped dict — no client, no prompts."""
    policy = base_policy()
    decision = admit(make_item(title="We're hiring!"), policy)
    assert decision.outcome == "rejected"


def test_o3_admission_module_imports_no_prompt_machinery():
    """No LLM/prompt/network machinery in kb/admission imports (AST check)."""
    import ast
    from pathlib import Path

    import kb.admission

    pkg_dir = Path(kb.admission.__file__).parent
    banned_prefixes = ("workflows", "hooks", "openai", "langgraph", "langchain")
    for py in pkg_dir.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(banned_prefixes), (py.name, name)
                assert "prompt" not in name.lower(), (py.name, name)


def test_o3_verbatim_hollow_words_survive():
    assert HOLLOW_WORDS == HOLLOW_WORDS_ZH + HOLLOW_WORDS_EN
    assert "赋能" in HOLLOW_WORDS_ZH
    assert "groundbreaking" in HOLLOW_WORDS_EN


# ---------------------------------------------------------------------------
# Integrity / degraded behavior (policy §2.5)
# ---------------------------------------------------------------------------


def test_missing_score_is_terminal_rejection():
    decision = admit(make_item(score=None), base_policy())
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "MISSING_SCORE"
    assert decision.evidence["raw_score"] is None


def test_missing_score_is_rejection_not_accept_even_with_p0_rescue():
    decision = admit(
        make_item(score=None, title="mcp langgraph agents", summary="mcp langgraph"),
        base_policy(),
    )
    assert decision.outcome == "rejected"
    assert "ACCEPTED" not in decision.reason_codes


def test_malformed_score_string_is_missing_score():
    decision = admit(make_item(score="9"), base_policy())
    assert decision.reason_codes[0] == "MISSING_SCORE"


def test_missing_summary_is_terminal():
    decision = admit(make_item(summary="   "), base_policy())
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "MISSING_SUMMARY"


def test_missing_published_at_is_terminal():
    decision = admit(make_item(published_at=None), base_policy())
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "MISSING_PUBLISHED_AT"


def test_malformed_enrichment_is_warning_not_terminal():
    decision = admit(make_item(tags="not-a-list"), base_policy())
    assert decision.outcome == "accepted"  # score gate alone decides
    assert "MALFORMED_ENRICHMENT" in decision.reason_codes
    assert decision.reason_codes[-1] == "MALFORMED_ENRICHMENT"


def test_malformed_metadata_is_warning_not_terminal():
    decision = admit(make_item(metadata_json={1, 2}), base_policy())
    assert decision.outcome == "accepted"
    assert "MALFORMED_METADATA" in decision.reason_codes
    assert decision.reason_codes[-1] == "MALFORMED_METADATA"


def test_warnings_never_change_rejection_outcome():
    decision = admit(make_item(score=3.0, tags=42), base_policy())
    assert decision.outcome == "rejected"
    assert decision.reason_codes == ("REJECTED_LOW_SCORE", "MALFORMED_ENRICHMENT")


# ---------------------------------------------------------------------------
# Score gate (A3 → A2 → A1 → A4)
# ---------------------------------------------------------------------------


def test_a3_low_source_cap_precedes_rescue():
    """discussion/news below raw 7.0 cannot be rescued by a P0 topic."""
    decision = admit(
        make_item(
            source_type="hackernews",
            score=6.5,
            title="mcp tool-use discussion",
            summary="mcp tool-use discussion thread about agent engineering",
        ),
        base_policy(),
    )
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "REJECTED_LOW_SCORE"
    assert "LOW_SOURCE_TYPE" in decision.reason_codes
    assert "RESCUED_BY_TOPIC" not in decision.reason_codes


def test_a2_p0_rescue_accepts_below_base():
    decision = admit(
        make_item(
            score=6.4,
            title="LangGraph deep dive",
            summary="langgraph workflow patterns",
            source_type="rss",
        ),
        base_policy(),
    )
    assert decision.outcome == "accepted"
    assert decision.reason_codes == ("ACCEPTED", "TOPIC_P0_BOOST", "RESCUED_BY_TOPIC")


def test_a2_blocked_by_low_confidence():
    decision = admit(
        make_item(
            score=6.4,
            title="LangGraph deep dive",
            summary="langgraph workflow patterns",
            source_type="rss",
            profile_confidence=0.3,
        ),
        base_policy(),
    )
    assert decision.outcome == "rejected"
    assert "RESCUED_BY_TOPIC" not in decision.reason_codes


def test_a1_base_accept_at_7_effective():
    decision = admit(neutral_item(score=7.0, source_type="rss"), base_policy())
    assert decision.outcome == "accepted"
    assert decision.reason_codes == ("ACCEPTED",)
    assert decision.evidence["topic_tier"] == "none"


def test_a1_p0_topic_adds_boost_code():
    decision = admit(
        make_item(score=8.5, summary="langgraph patterns", source_type="rss"),
        base_policy(),
    )
    assert decision.outcome == "accepted"
    assert decision.reason_codes == ("ACCEPTED", "TOPIC_P0_BOOST")


def test_a4_rejects_below_threshold():
    decision = admit(make_item(score=5.0, source_type="rss"), base_policy())
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "REJECTED_LOW_SCORE"


def test_p2_only_match_gets_no_rescue():
    """A P2-only match must pass the base gate alone — no A2 rescue."""
    decision = admit(
        make_item(score=6.5, source_type="rss",
                  title="Quarterly platform notes",
                  summary="technical communication and business context notes"),
        base_policy(),
    )
    assert decision.outcome == "rejected"
    assert "RESCUED_BY_TOPIC" not in decision.reason_codes
    assert decision.evidence["topic_tier"] == "p2"


# ---------------------------------------------------------------------------
# Duplicates (policy §2.4)
# ---------------------------------------------------------------------------


def test_duplicate_id_is_rejected_with_pointer():
    decision = admit(
        make_item(), base_policy(), dedup=DedupState(decided_item_ids=("horizon:abc-123",))
    )
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "DUPLICATE_ID"
    assert decision.duplicate_of == "horizon:abc-123"


def test_duplicate_url_ignores_scheme_and_trailing_slash():
    decision = admit(
        make_item(url="https://example.com/posts/langgraph-eval/"),
        base_policy(),
        dedup=DedupState(decided_urls=("http://Example.com/posts/langgraph-eval",)),
    )
    assert decision.outcome == "rejected"
    assert decision.reason_codes[0] == "DUPLICATE_URL"
    assert decision.duplicate_of == "http://Example.com/posts/langgraph-eval"


def test_distinct_urls_same_story_fp_is_not_deduped():
    decision = admit(
        make_item(url="https://example.com/posts/langgraph-eval-2"),
        base_policy(),
        dedup=DedupState(decided_urls=("https://example.com/posts/langgraph-eval",)),
    )
    assert decision.outcome == "accepted"
    assert "DUPLICATE_URL" not in decision.reason_codes


def test_duplicate_check_runs_before_integrity():
    """A malformed-but-duplicated item still gets the dedup verdict."""
    decision = admit(
        make_item(score=None),
        base_policy(),
        dedup=DedupState(decided_item_ids=("horizon:abc-123",)),
    )
    assert decision.reason_codes[0] == "DUPLICATE_ID"


# ---------------------------------------------------------------------------
# Low confidence (policy §2.6)
# ---------------------------------------------------------------------------


def test_missing_confidence_on_ai_match_warns():
    decision = admit(make_item(profile_confidence=None), base_policy())
    assert "LOW_CONFIDENCE_MATCH" in decision.reason_codes


def test_low_confidence_warns_and_blocks_rescue_only():
    decision = admit(
        make_item(score=6.4, source_type="rss", profile_confidence=0.4,
                  title="LangGraph", summary="langgraph"),
        base_policy(),
    )
    assert "LOW_CONFIDENCE_MATCH" in decision.reason_codes
    assert decision.outcome == "rejected"
    high = admit(
        make_item(score=8.0, source_type="rss", profile_confidence=0.4,
                  title="LangGraph", summary="langgraph"),
        base_policy(),
    )
    assert high.outcome == "accepted"


def test_source_override_ignores_confidence():
    decision = admit(
        make_item(score=6.4, source_type="rss", profile_method="source_override",
                  profile_confidence=None, title="LangGraph", summary="langgraph"),
        base_policy(),
    )
    assert "LOW_CONFIDENCE_MATCH" not in decision.reason_codes
    assert decision.outcome == "accepted"


# ---------------------------------------------------------------------------
# Replay invariant and evidence ordering (policy §3)
# ---------------------------------------------------------------------------


def test_replay_reproduces_outcome_and_reason_codes():
    policy = base_policy()
    items = [
        make_item(id="horizon:r1", score=6.4, summary="langgraph eval",
                  source_type="rss"),
        make_item(id="horizon:r2", score=3.0),
        make_item(id="horizon:r3", title="We're hiring!"),
        make_item(id="horizon:r4", score=None),
    ]
    for item in items:
        first = admit(item, policy)
        replay = admit(item, policy)
        assert (replay.outcome, replay.reason_codes) == (first.outcome, first.reason_codes)
        row = json.loads(json.dumps(first.to_row()["evidence_json"] and first.to_row()))
        assert row["reason_codes"] == list(first.reason_codes)


def test_evidence_checks_follow_phase_order():
    # score=5.0 + 0.0 (blog) → pure A4 path: every phase is exercised.
    decision = admit(neutral_item(score=5.0, source_type="rss"), base_policy())
    phases = [check["phase"] for check in decision.evidence["checks"]]
    assert phases == sorted(
        phases,
        key=["dedup", "integrity", "noise", "score_gate"].index,
    )
    assert decision.evidence["checks"][-1]["rule"] == "a4_reject"


def test_evidence_is_bounded_and_json_serializable():
    decision = admit(make_item(), base_policy())
    blob = json.dumps(decision.evidence, ensure_ascii=False, sort_keys=True)
    assert len(blob) < 4096
    assert json.loads(blob) == decision.evidence


def test_to_row_shape_matches_ledger_contract():
    decision = admit(make_item(), base_policy())
    row = decision.to_row()
    assert row["item_id"] == "horizon:abc-123"
    assert row["outcome"] == "accepted"
    assert row["policy_id"] == "admission-policy"
    assert isinstance(row["reason_codes"], list)
    assert json.loads(row["evidence_json"])["checks"]


def test_duplicate_of_lives_in_column_not_evidence():
    decision = admit(
        make_item(), base_policy(), dedup=DedupState(decided_item_ids=("horizon:abc-123",))
    )
    assert decision.duplicate_of == "horizon:abc-123"
    assert "duplicate_of" not in decision.evidence
