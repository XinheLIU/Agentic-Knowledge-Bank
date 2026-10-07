# P0 Personal Admission Policy (ai-kb · Horizon cutover)

> Last updated: 2026-10-04
> Status: **Accepted (design for ticket 03)** · Owner: ticket [03](../../../.scratch/horizon-kb-design/issues/03-design-personal-admission-policy.md)
> Inputs: [`design.md`](design.md) (D-1..D-3, §4 field map, §5 retirements) · [`asset-audit-model.md`](asset-audit-model.md) (candidate/asset identity, ledger shape, reason-code registry — wins on representation conflicts) · the Horizon profile `ai-kb-personal/` shipped with Information Assistant (`information_assistant/resources/horizon-profiles/ai-kb-personal/`, successor to the retired v0.7.0 `workflows/relevance_profile.yaml`) · Horizon contract research [`.scratch/horizon-kb-design/research/horizon-contract-596e2b1.md`](../../../.scratch/horizon-kb-design/research/horizon-contract-596e2b1.md) · discovery O1/O3.
> Resolves: ticket 03 closure criteria. Owning implementation tickets: [09](../../../.scratch/horizon-kb-design/issues/09-implement-personal-admission.md) (profile + function), [07](../../../.scratch/horizon-kb-design/issues/07-implement-sqlite-asset-store.md) (persistence), [10](../../../.scratch/horizon-kb-design/issues/10-build-auditable-run-ingest.md) (run accounting).
> Division of authority with ticket 02 (agreed in asset-audit-model §3.2): `kb/model.py` owns the reason-code **registry** (membership, namespaces); this document owns policy-code **semantics**. No second vocabulary is introduced here.

---

## 0. Scope and non-goals

**In scope (P0):** (a) the Horizon profile `ai-kb-personal/` — owned by Information
Assistant, not KB — loaded by the pinned Horizon runtime; (b) a deterministic, pure, **per-item admission
function** evaluated in this repo after mapping, producing one auditable ledger row
per candidate (O1), with **executable negative patterns** (O3), replacing the retired
`hooks/check_quality.py` (deleted with the legacy path, ticket 16) as the deterministic quality gate.

**Non-goals (P0):** no additional LLM calls for admission (Horizon's 0–10
`analysis.score`, its reason, summary, tags, and classification confidence are the
only AI outputs consumed); no re-ranking beyond sort order; no post-hoc 115-point
quality rubric.

**Concern split (authoritative):**

| Concern | Owner in P0 | Rationale |
|---|---|---|
| Topic *routing* (which profile handles an item) | Horizon (`ai-kb-personal` profile, `match.md`) | Horizon-native, per ticket 09's "project-owned Horizon profile" requirement |
| Topic *weighting* in AI scoring | Horizon (`analysis.md` rubric: P0/P1/P2 tiers) | personalization enters where the model scores |
| Summary/enrichment shape | Horizon (`enrichment.md`, blocks) | Horizon-native artifact pipeline |
| Numeric thresholds, rescue, source boosts, caps | **Local** (`kb/admission/policy.py`) | must be deterministic, testable, versioned — not prompt-dependent |
| Negative-pattern detection | **Local** (typed specs, §2.3) | O3 requires code, not prompt |
| Dedup, low-confidence handling, decision records | **Local** (records shaped per asset-audit-model §3) | audit invariants live with the store |

---

## 1. Horizon-native profile (P0, collection-owner)

### 1.1 Files and configuration

The profile is versioned **with the collection owner** (Information Assistant,
`information_assistant/resources/horizon-profiles/`), not inside the Horizon
checkout, and loaded via Horizon's absolute-path `profiles_dir` (supported:
`ProfileRegistry.load`
uses the path as-is when absolute; `src/processing/profiles.py:84-119`):

```text
information_assistant/resources/horizon-profiles/
└── ai-kb-personal/
    ├── profile.json      # id, name, display_names, file refs, content limits, enrichment blocks
    ├── match.md          # routing statement (ai_match consistency; default routing is source config)
    ├── analysis.md       # 0–10 rubric with P0/P1/P2 topic tiers and mechanism requirement
    └── enrichment.md     # block guidance (summary primary; background/takeaway)
```

Horizon `config.json` (written by ticket 06 packaging, validated by
`hz_validate_config` at startup):

```json
{
  "processing": {
    "profiles_dir": "<information-assistant>/resources/horizon-profiles",
    "default_profile": "ai-kb-personal",
    "profile_settings": {
      "ai-kb-personal": { "threshold": null, "topic_dedup": true }
    }
  }
}
```

- `default_profile = "ai-kb-personal"` routes every fetched item to the personal
  profile; `match.md` keeps `ai_match` classification consistent with that default.
- `threshold: null` means **Horizon applies no score filter**: every scored item
  reaches this side (`hz_get_run_stage(run_id, "scored")` plus `"enriched"`) and the
  local policy is the **single gatekeeper**. This preserves per-item auditability for
  every candidate (O1) — filtering upstream would silently discard sub-threshold
  items before any admission record exists. `topic_dedup: true` keeps Horizon's
  within-run story dedup (this side does not re-implement it; §2.4). Enrichment cost
  is accepted at current volume (automation limit ≈20 items/day, AGENTS.md CLI
  contract); revisiting the upstream threshold is a policy-version bump, not a code
  change.
- The profile files are inputs to `runs.config_hash` (asset-audit-model §6), so every
  run is auditable against the exact profile text that produced it.

### 1.2 Profile content (derived from `relevance_profile.yaml`)

- **`match.md`**: use for agent engineering, LangGraph/LangChain workflows, tool-use,
  MCP, browser/computer-use agents, data agents, RAG knowledge systems, production
  evaluation (P0), and the P1 context list (§1.4); not for finance-first coverage,
  hiring/conference administration, or promotional launches.
- **`analysis.md`** rubric keeps Horizon's 0–10 anchors but re-weights guidance:
  P0-topic items with concrete mechanisms (code, benchmarks, architecture, evals)
  score 7–10; P1-topic items 5–8; generic AI discourse / business commentary without
  mechanism ≤4; pure announcements ≤3. Instructs 3–5 specific tags, preferring the
  learning-tag vocabulary (§1.4) where applicable. This is **guidance to the model
  only** — the deterministic admission rules below never trust it as a rule.
- **`enrichment.md`**: blocks `summary` (primary), `background`, `takeaway` —
  matching the `tech-blog` block pattern, guided toward "what should the learner do
  with this".

### 1.3 Legacy-profile mapping (complete, P0/P1/P2 included)

| Legacy concept | Horizon-native P0 use | Local P0 use |
|---|---|---|
| `focus_topics.p0_must_learn` (10 topics) | `analysis.md` top rubric tier; `match.md` routing | `topic_tier="p0"` evidence; A2 rescue eligibility (§2.2) |
| `focus_topics.p1_valuable_context` (8 topics) | `analysis.md` middle tier | `topic_tier="p1"` evidence; **no** threshold change |
| `focus_topics.p2_background` (3 topics: `generic ai discourse`, `business context`, `technical communication`) | `analysis.md` bottom tier (≤4 without mechanism) | `topic_tier="p2"` evidence; **no rescue, no boost** — a P2-only match must pass the base gate alone (§2.2), and the tier is retained in every decision record for digest/audit down-ranking |
| `learning_tracks` (9 values) | not used by Horizon (no field) | retained as evidence labels only (P1 re-derivation input) |
| `preferred_source_types` high/medium/low | not used by Horizon (fetch sources ≠ quality) | source-class boosts + low-source cap (§1.5, §2.2) |
| `negative_patterns` (4 labels) | `analysis.md` scoring guidance ("do not reward announcements/hype") — **non-authoritative** | executable detector specs (§2.3) — **authoritative** |
| `learning_tag_allowlist` (21 tags) | `analysis.md` tag-vocabulary guidance | dropped as a rule; returns in P1 |

All topic/pattern/track strings are carried over **verbatim** (verified against
`relevance_profile.yaml` by ticket 09's tests).

### 1.4 Verbatim lists

- `p0`: `agent engineering`, `langgraph`, `langchain`, `tool-use`, `mcp`,
  `browser agents`, `computer-use agents`, `data agents`, `rag knowledge systems`,
  `production evaluation`
- `p1`: `llm engineering`, `ai coding systems`, `local model workflows`,
  `applied ml`, `reinforcement learning`, `quantitative analysis`,
  `data science methodology`, `engineering architecture`
- `p2`: `generic ai discourse`, `business context`, `technical communication`
- `negative_patterns`: `hype without technical mechanism`,
  `hiring or conference administration`, `shallow product launch`,
  `generic enterprise AI commentary`
- `learning_tracks`: `agent-systems`, `langgraph-workflows`, `data-agents`,
  `rag-knowledge-systems`, `evaluation`, `local-model-serving`,
  `ml-rl-foundations`, `quant-data-science`, `engineering-leadership`

### 1.5 Source-type mapping (Horizon fetch enum → policy source class)

Emitted by the mapper (ticket 08) as `policy_source_class`:

| Horizon `source_type` | Policy class | Boost |
|---|---|---|
| `github`, `openbb`, `ossinsight` | `repository` | +1.0 (high) |
| `rss` | `blog` | 0.0 (medium) — cannot be classified deeper locally |
| `hackernews`, `reddit` | `discussion` | −0.5 (low) |
| `telegram`, `twitter`, `gdelt`, `google_news` | `news` | −0.5 (low) |

The legacy taxonomy (`tutorial`, `paper`, `benchmark`, …) needs item-level
classification P0 cannot do deterministically; P1 may widen via profile work.

---

## 2. Deterministic admission function

### 2.1 Signature, phases, and exact order

```python
def admit(item: MappedItem, policy: AdmissionPolicy) -> AdmissionDecision:
    """Pure; no I/O; no LLM. Returns outcome + ordered reason codes for the ledger."""
```

Evaluation has **four terminal phases** (ordered, short-circuiting — the first
terminal rule ends evaluation and fixes the `outcome`) and one **parallel warning
channel** that never changes an outcome:

```text
Phase 0 dedup        → terminal: DUPLICATE_ID / DUPLICATE_URL            [asset-model §1.2]
Phase 1 integrity    → terminal: MISSING_SCORE / MISSING_SUMMARY / MISSING_PUBLISHED_AT
Phase 2 noise        → terminal: NEG_* (first matching spec)
Phase 3 score gate   → terminal: accept (A3 → A2 → A1) or reject (A4)

Warnings (collected throughout; appended to the FINAL row's reason_codes array;
          never alter the outcome):
  MALFORMED_ENRICHMENT   malformed tags/artifacts/analysis.reason (coerced, §2.5)
  MALFORMED_METADATA     non-serializable metadata (coerced to {}, §2.5)
  LOW_CONFIDENCE_MATCH   classification confidence missing/low on ai_match (§2.6)

Evidence-only (never reason codes; carried in evidence_json):
  TOPIC_TIER             p0 | p1 | p2 | none
  SOURCE_CLASS           repository | blog | discussion | news
```

Two consequences of this separation, resolving the known contradictions:

- `MALFORMED_*` are **warnings, not terminal rules** — malformed enrichments can be
  accepted (the score gate decides) and the warning rides on whatever row results.
- The low-source cap is evaluated **before** the P0 rescue (**A3 precedes A2**), so a
  low-source item below 7.0 raw can never be rescued — matching the legacy
  `_apply_rule_caps` ordering deterministically. Warning codes (`MALFORMED_*`,
  `LOW_CONFIDENCE_MATCH`) are registered in the `kb/model.py` registry's integrity /
  policy namespaces with semantics defined here; being in `reason_codes` does **not**
  make a code terminal — only §2.1 phases decide outcomes.

### 2.2 Score gate (terminal rules, evaluated A3 → A2 → A1 → A4)

`effective_score = horizon_score + source_class_boost` (boost from §1.5):

| Rule | Condition | Outcome | reason_codes (ordered) |
|---|---|---|---|
| A3 low-source cap | `policy_source_class ∈ {discussion, news}` and `horizon_score < 7.0` | **rejected** | `["REJECTED_LOW_SCORE", "LOW_SOURCE_TYPE"]` |
| A2 P0 rescue | `effective_score ≥ 6.0` and `topic_tier == "p0"` and A3 condition false and not low-confidence-blocked (§2.6) | **accepted** | `["ACCEPTED", "TOPIC_P0_BOOST", "RESCUED_BY_TOPIC"]` |
| A1 base accept | `effective_score ≥ 7.0` | **accepted** | `["ACCEPTED"]` (+ `"TOPIC_P0_BOOST"` when `topic_tier == "p0"`) |
| A4 otherwise | — | **rejected** | `["REJECTED_LOW_SCORE"]` |

7.0 equals Horizon's wizard default for `tech-news` (`src/setup/wizard.py:317`); A2
reproduces the legacy "P0 match floors at save-for-context" as an accept floor one
point below base; A3 reproduces "discussion/news without mechanism cap at
low-priority" as a no-boost hard cap. P1/P2 tiers get **no** threshold modification —
their role is evidence and (for P2) analysis-side rubric weighting only. Threshold
constants live in `kb/admission/policy.py`, versioned as `admission-policy@0.1.0` (a policy revision, independent of the project version) 
(policy_id `admission-policy`, matching asset-audit-model §3.1).

### 2.3 Executable negative patterns (O3, terminal phase 2)

Each legacy label becomes a **typed detector spec** (data in
`kb/admission/patterns.py`); no prompt path exists in the admission module (O3 test:
the module references no LLM client and rejection occurs with the AI layer stubbed
out). Terminal: the **first** matching spec rejects the item.

| Pattern label | Detector spec (deterministic) | reason_codes |
|---|---|---|
| hype without technical mechanism | (title+summary) contains ≥2 hollow words from `kb/admission/hollow_words.py` (retired `check_quality` ZH/EN lists, verbatim) **and** none of the mechanism keywords (`benchmark`, `评测`, `ablation`, `architecture`, `架构`, `open-source`, `github.com`, `paper`, `论文`, `API`, `schema`, `eval`) | `["NEG_HYPE_NO_MECHANISM"]` |
| hiring or conference administration | case-insensitive regex `(hiring\|we're hiring\|join our team\|招聘\|call for (papers\|speakers)\|cfp\|registration (is\|now) open)` on title | `["NEG_HIRING_CONFERENCE"]` |
| shallow product launch | title matches `(launch(es\|ed)?\|releases?\|announces?\|now available\|raising\|series [a-c])` **and** `horizon_score < 8.0` **and** summary length < 120 chars | `["NEG_SHALLOW_LAUNCH"]` |
| generic enterprise AI commentary | summary contains ≥2 of (`enterprise`, `transform`, `digital`, `strategy`, `行业`, `企业`, `战略`, `赋能`) **and** no mechanism keywords **and** `topic_tier != "p0"` | `["NEG_GENERIC_ENTERPRISE"]` |

The matched pattern **label** (the legacy string, verbatim) is recorded in
`evidence_json.pattern` — the ledger has no free-text detail column. Adding a pattern
= adding a spec, never prompt text. Rejected-by-pattern items keep their full
evidence and are never silently dropped.

### 2.4 Duplicates (exact match with asset-audit-model §1.2 precedence)

Dedup runs **before** any scoring rule, in this order; the first match wins:

| Precedence | Condition | Outcome | reason_codes |
|---|---|---|---|
| 0 | same `run_id` replayed | **not an admission decision** — store idempotency (ticket 07): nothing appended, nothing mutated | — |
| 1 | same `item_id` already decided in this run, or already persisted from an earlier run | **rejected** candidate; `duplicate_of` = existing candidate/asset id | `["DUPLICATE_ID"]` |
| 2 | normalized `url` already an accepted asset, or already decided (any outcome) in this run | **rejected** candidate; `duplicate_of` = earlier candidate/asset id | `["DUPLICATE_URL"]` |
| 3 | same `story_fp`, different URL | **no dedup**: fresh admission decision; retrieval joins via `edges(kind='same_story')` (resolves design.md K4 lossiness) | — |

URL normalization (strip `http(s)://`, trailing `/`, lowercase host): **spec** here,
single algorithm owner `kb/model.py` alongside `story_fp` — the policy calls it,
never re-implements it. Within-run story dedup stays Horizon's
(`topic_dedup: true`, §1.1).

### 2.5 Integrity and degraded behavior (terminal phase 1)

| Condition (observed in mapped item) | Outcome | reason_codes | Behavior |
|---|---|---|---|
| `processing.analysis` absent or `score is None` (AI failed upstream; full-enrichment failure drops the enriched stage) | **rejected** | `["MISSING_SCORE"]` | never silently passed — the legacy reviewer's auto-pass-on-LLM-error is deliberately not reproduced |
| `summary` empty/whitespace while score exists | **rejected** | `["MISSING_SUMMARY"]` | evidence: `{"missing": "summary"}` |
| `published_at` missing (upstream forbids; reachable only via hand-built fixtures) | **rejected** | `["MISSING_PUBLISHED_AT"]` | same family as missing score |
| mapper could not produce typed store input | **failed** (ledger outcome, non-terminal — a later run re-decides; asset-audit-model §2) | `["MAP_FAILED"]` | transport/mapping namespace, ticket 01 contract research |
| `tags` non-list, `analysis.reason` non-string, `artifacts` not a dict | **no terminal effect** | warning `MALFORMED_ENRICHMENT` appended to the final row's codes | malformed fields coerced to `[]`/NULL; a good score is not erased |
| `metadata` not JSON-serializable | **no terminal effect** | warning `MALFORMED_METADATA` | coerced to `{}` |
| classification `confidence` missing or low | **no terminal effect by itself** | warning `LOW_CONFIDENCE_MATCH` | deterministic rule effects in §2.6 |
| whole-run AI unavailable | **no per-item admission occurs** | run-level `ENRICHMENT_UNAVAILABLE` on the `runs` row (ticket 10) | run records `status=partial_failure`/`failure`; zero accept rows can exist without score rows — invariant-checked |

**Rule: missing AI output can never produce an accepted decision.** Rejected items
still retain id, URL, title, raw score, and full evidence in the ledger.

### 2.6 Low-confidence matches (deterministic)

- **Confidence source:** `processing.classification.confidence` (0.0–1.0, nullable;
  present on `ai_match`, typically absent on `source_override`) — the only
  confidence signal in the pinned Horizon contract.
- **Threshold:** `confidence < 0.5`, or `confidence is None` on `ai_match` (missing is
treated as 0 — never silently passed), ⇒ warning `LOW_CONFIDENCE_MATCH`.
- **Deterministic effect:** a low-confidence item **loses A2 rescue eligibility** and
  must pass the **base gate (A1, ≥7.0 effective)** to be accepted. Being
  low-confidence is never by itself a rejection — the score gate still decides.
- **`source_override` routing:** confidence is ignored (the route was deterministic
  source config, not a model judgment); profile identity is still recorded as
  evidence.
- **Registry note:** `LOW_CONFIDENCE_MATCH` is a policy-namespace code added to the
  `kb/model.py` registry by the requested one-place extension (asset-audit-model
  §3.2); semantics are owned by this subsection.

---

## 3. Decision records (reconciliation with ticket 02)

One `admissions` row per `(run_id, item_id)` exactly as asset-audit-model §3/§6 —
this policy introduces **no second representation**:

- `outcome` ∈ `accepted | rejected | failed` as produced by this policy
  (`supersede` is ticket 02's, never emitted by admission).
- `policy_id = "admission-policy"`, `policy_version = "0.1.0"` (bumped on any
  threshold/detector change; membership of codes stays owned by `kb/model.py` — O2).
- **`reason_codes` is an ordered JSON array** (asset-audit-model §3.2, binding for
  tickets 07/09): terminal codes appear in phase order, warnings appended last. All
  codes are drawn from the shared registry namespaces:

| This policy's terminal outcome | `reason_codes` | Registry namespace |
|---|---|---|
| A1 accept | `["ACCEPTED"]` (± `"TOPIC_P0_BOOST"`) | policy decision |
| A2 accept | `["ACCEPTED", "TOPIC_P0_BOOST", "RESCUED_BY_TOPIC"]` | policy decision |
| A3 reject | `["REJECTED_LOW_SCORE", "LOW_SOURCE_TYPE"]` | policy decision |
| A4 reject | `["REJECTED_LOW_SCORE"]` | policy decision |
| Phase 2 reject | `["NEG_*"]` | policy negative patterns (O3) |
| URL/ID duplicate | `["DUPLICATE_URL"]` / `["DUPLICATE_ID"]` (+ warnings) | dedup; `duplicate_of` set |
| Phase 1 reject | `["MISSING_SCORE"]` / `["MISSING_SUMMARY"]` / `["MISSING_PUBLISHED_AT"]` | integrity |
| Mapper failure | outcome `failed`, `["MAP_FAILED"]` | transport/mapping |
| Warnings (non-terminal) | appended: `MALFORMED_ENRICHMENT`, `MALFORMED_METADATA`, `LOW_CONFIDENCE_MATCH` | integrity / policy |

- **`evidence_json` (bounded, re-derivable; shape owned by this §3 per
  asset-audit-model §3.1)** is one normalized object:

```json
{
  "checks": [
    {"phase": "dedup", "rule": "url", "hit": false},
    {"phase": "integrity", "rule": "missing_score", "hit": false},
    {"phase": "noise", "rule": "hype_without_technical_mechanism", "hit": false},
    {"phase": "score_gate", "rule": "a2_rescue", "hit": true}
  ],
  "raw_score": 6.4, "effective_score": 7.4, "boost": 1.0,
  "topic_tier": "p0", "matched_topics": ["langgraph"],
  "source_class": "repository", "confidence": 0.81,
  "warnings": [], "pattern": null, "summary_len": 214, "tags": ["langgraph", "agent"]
}
```

  `checks` is the ordered per-phase evaluation trace (phase, rule, hit/miss), giving
  both an ordered-list and a one-normalized-row-per-fact reading from the single
  stored row. `pattern` carries the matched legacy label (§2.3); `duplicate_of` lives
  in its own ledger column, not inside evidence.

**Re-derivability invariant (tested):** replaying `admit()` with the stored inputs
and the same `policy_version` reproduces the stored `outcome` and `reason_codes`
array exactly.

---

## 4. What replaces `hooks/check_quality.py` (deleted with the legacy path, ticket 16)

Deterministic quality control is the **admission decision record itself**, evaluated
at ingest against the versioned policy — not a post-hoc six-dimension rubric over
fields that no longer exist (R-D7). Concretely:

- the retired `check_quality` hollow-word lists survive **verbatim** in
  `kb/admission/hollow_words.py` and are re-used by the §2.3 hype detector;
- `check_quality.py` is deleted with the legacy path (ticket 16); no P1 dependency is
  required (design.md B4 resolved by this substitution);
- summary-length and tag-precision instincts live on as: `MISSING_SUMMARY` (empty
  summary), `MALFORMED_ENRICHMENT` (bad tags/reason), and the §2.3 detectors — each
  deterministic and audit-visible in the ledger.

## 5. O1 / O3 proof obligations (implemented and tested in ticket 09)

- **O1 (batch review gone):** `admit()` is invoked once per item; a property-style
  test asserts per-item independence (changing item k's inputs cannot change item
  j's decision) and that no code path consumes a batch-level score — the reviewer
  node's `analyses[:5]` sample veto has no successor anywhere in `kb/`. Upstream
  `threshold: null` (§1.1) guarantees every candidate reaches an admission record.
- **O3 (prompt-only noise filtering gone):** the four legacy pattern labels each map
  to a §2.3 spec with a unit test; rejection occurs with the AI client layer fully
  stubbed out; the admission module imports no prompt/LLM machinery (grep-checked).
  The `analysis.md` mentions of noise are guidance only — admission never reads
  prompts.
