## Context

> Last updated: 2026-05-24

The current scoring path mixes several concepts:

```text
Analyzer relevance_score  = generic AI/LLM/Agent relatedness
Analyzer score            = loose quality/depth/importance signal
Reviewer score            = batch-level quality score over first 5 analyses
Quality hook              = maps score directly to technical depth
```

This creates skew because the system does not distinguish between popularity, technical depth, personal fit, and study actionability. It also penalizes the learning-intent tags proposed in `docs/personal-knowledge-strategy-plan.md` because the current valid tag lists only include broad AI topic tags.

## Goals / Non-Goals

**Goals:**
- Rank each candidate by personal learning value from a configurable user relevance profile.
- Let the user configure current status, focus topics, priority tiers, source preferences, learning tracks, and negative/noise patterns without editing Python code.
- Preserve a readable explanation of why an item matters.
- Produce a useful reading priority: `study-now`, `save-for-context`, `skim`, `low-priority`, or `skip`.
- Support learning-intent tags without breaking existing broad tags.
- Make scores spread meaningfully across low, medium, and high priority.
- Keep existing articles valid and keep current required fields present.

**Non-Goals:**
- Do not change GitHub/RSS collection strategy in this change.
- Do not add seed repositories or star velocity logic in this change.
- Do not build weekly review outputs or UI reading queues in this change.
- Do not migrate existing `knowledge/articles/*.json` files.
- Do not introduce new dependencies.

## Decisions

### Decision 1: relevance policy lives in a YAML profile

**Choice:** Add a repo-local relevance profile, initially `workflows/relevance_profile.yaml`, loaded by analyzer/reviewer at runtime. The default profile should encode the current strategy plan, but it must be user-editable.

Suggested shape:

```yaml
profile_id: default
user_status: "AI/agent engineering learner building a personal technical intelligence system"
updated_at: "2026-05-24"

focus_topics:
  p0_must_learn:
    - agent engineering
    - langgraph
    - langchain
    - tool-use
    - mcp
    - browser agents
    - computer-use agents
    - data agents
    - rag knowledge systems
    - production evaluation
  p1_valuable_context:
    - llm engineering
    - ai coding systems
    - local model workflows
    - applied ml
    - reinforcement learning
    - quantitative analysis
    - data science methodology
    - engineering architecture
  p2_background:
    - generic ai discourse
    - business context
    - technical communication

learning_tracks:
  - agent-systems
  - langgraph-workflows
  - data-agents
  - rag-knowledge-systems
  - evaluation
  - local-model-serving
  - ml-rl-foundations
  - quant-data-science
  - engineering-leadership

preferred_source_types:
  high:
    - repository
    - tutorial
    - documentation
    - paper
    - benchmark
  medium:
    - blog
    - product
  low:
    - discussion
    - news

negative_patterns:
  - hype without technical mechanism
  - hiring or conference administration
  - shallow product launch
  - generic enterprise AI commentary
```

The implementation should treat missing config as a recoverable condition by falling back to a conservative built-in default equivalent to the checked-in profile.

**Reasoning:** Personal relevance changes as the owner changes. Hard-coding the roadmap in the prompt would immediately become stale and would make this feature personal to one snapshot rather than generally useful.

### Decision 2: keep `relevance_score`, add explicit personal scoring fields

**Choice:** Keep `relevance_score` for compatibility, but define it as personal relevance going forward. Add explicit component scores:

```json
{
  "personal_fit_score": 0.86,
  "technical_depth_score": 0.75,
  "actionability_score": 0.90,
  "source_credibility_score": 0.80,
  "novelty_score": 0.65,
  "priority_score": 84,
  "reading_priority": "study-now"
}
```

All component scores are normalized to `0.0..1.0`; `priority_score` is `0..100`; compatibility `score` remains `1..10` and is derived from priority unless the implementation keeps a model-provided value with equivalent semantics.

**Reasoning:** Existing validators, fixtures, UI, and article consumers expect `relevance_score` and `score`. Replacing them outright would create unnecessary churn. Explicit new fields remove ambiguity for future work.

### Decision 3: use a weighted score with configurable rule caps

**Choice:** The final priority should be based on:

```text
priority_score =
  35% personal_fit
+ 25% technical_depth
+ 20% actionability
+ 10% source_credibility
+ 10% novelty
- penalties
```

The implementation may ask the LLM for these values directly, compute them deterministically from LLM output, or combine both. It must normalize and clamp outputs.

Rule caps should prevent obvious skew. The default caps should come from the relevance profile, with these built-in defaults:

| Condition | Cap / floor |
|---|---|
| Generic discussion or news with no technical mechanism/practice signal | max `low-priority` |
| Low-star or weakly described repository without exact topic/trusted author/tutorial/reference value | max `skim` |
| Exact P0 topic with tutorial/reference architecture value | at least `save-for-context` unless broken/duplicate |
| Clearly irrelevant, broken, duplicate, or empty item | `skip` |
| Uncertain but plausibly relevant item | not `skip`; use `low-priority` |

**Reasoning:** A pure weighted formula can still lie. Rule caps encode policy boundaries that matter more than small score differences.

### Decision 4: separate broad tags from learning-intent tags

**Choice:** Keep `tags` for broad retrieval facets and add `learning_tags` for why the item matters to the owner.

Broad `tags` remain compact, e.g.:

```json
"tags": ["agent", "rag", "evaluation"]
```

Learning tags include policy-oriented labels:

```json
"learning_tags": ["langgraph", "agent-harness", "reference-architecture"]
```

The implementation should allow at least these learning tags:

```text
agent-harness, langgraph, langchain, data-agent, mcp, tool-use,
browser-agent, computer-use, evaluation, repo-tutorial,
reference-architecture, paper-to-code, production-rag, local-llm,
quant-ai, business-context, implementation-pattern,
architecture-reference, production-lesson, research-method, noise
```

**Reasoning:** Overloading `tags` makes retrieval noisy and causes quality scoring conflicts. Separating them keeps backward compatibility and enables personal retrieval.

### Decision 5: add `source_type` and `learning_track`

**Choice:** Store source type separately from topic.

Allowed `source_type` values:

```text
repository, paper, blog, discussion, benchmark, tutorial, product, news, documentation, unknown
```

Allowed `learning_track` values:

```text
agent-systems, langgraph-workflows, data-agents, rag-knowledge-systems,
evaluation, local-model-serving, ml-rl-foundations, quant-data-science,
engineering-leadership, business-context, background
```

**Reasoning:** `source` currently mixes transport and origin (`github`, `rss:<name>`). `category` is too broad. `source_type` and `learning_track` make filtering and future review outputs straightforward.

### Decision 6: make summaries answer study value, not just item description

**Choice:** Analyzer summaries and supporting fields should capture:

- core idea
- technical mechanism
- personal learning value
- suggested learning action
- confidence

Persist the structured parts as:

```json
{
  "relevance_reason": "为什么它对我的路线有价值",
  "suggested_action": "clone-and-study | deep-read | skim | archive | skip",
  "confidence": 0.82
}
```

**Reasoning:** The human question is not only “what is this?” but “what should I do with it next?”

### Decision 7: quality hook should score alignment with policy

**Choice:** `hooks/check_quality.py` should stop using old broad-tag precision as the main tagging standard. It should reward:

- personal relevance fields present and in range
- clear relevance reason
- actionable suggested action
- valid broad tags and/or valid learning tags
- source type and learning track present

It may keep summary and hollow-word checks, but should not let a long generic summary dominate quality.

**Reasoning:** The hook is a gate and feedback tool. If it rewards generic polish more than personal usefulness, it reinforces the skew.

## Risks / Trade-offs

- **Schema expansion risk:** More fields increase prompt and parsing complexity. Mitigation: keep new fields optional in validation for old articles, but require organizer defaults for new articles.
- **LLM calibration risk:** Models may cluster scores around 0.7. Mitigation: prompt with explicit priority bands and add deterministic normalization/caps.
- **Tag sprawl risk:** Learning tags may grow too quickly. Mitigation: start with a fixed allowlist and map unknown tags to broad tags or drop them.
- **Compatibility risk:** Existing consumers may only read `score` and `relevance_score`. Mitigation: keep both fields and derive them from new semantics.
