# Personal Knowledge Strategy Plan

> Last updated: 2026-06-23

> **v0.7.0 update:** the "ranked reading queue" described below is now delivered by
> `workflows/digest.py` — a daily email of `study-now` / `save-for-context` items,
> ranked by `priority_score`. See README "Email Digest".

## Summary

The knowledge base should shift from generic AI news collection to high-recall personal technical intelligence for a specific learning roadmap.

The current system collects many AI-adjacent items, but it does not yet reliably distinguish between content that is popular, content that is technically meaningful, and content that is directly useful for the owner of this knowledge base. The strategy should optimize for **coverage + relevance**: capture broadly inside the owner’s real interest boundary, preserve potentially useful signals, then rank and explain them so a human can decide what to study.

The personal relevance center should be:

- Agent engineering, especially LangGraph, LangChain, tool-use, MCP, browser/computer-use agents, and harness systems
- Data agents, RAG, knowledge systems, and production evaluation
- Applied ML, reinforcement learning, quantitative analysis, and data science methodology
- Engineering architecture, AI development workflow, and practical full-stack implementation
- Business analysis, technical communication, and personal branding where they connect to AI capability building

## Diagnosis

The source mix is skewed. Most stored items come from broad community feeds such as Reddit and Hacker News, while official blogs, framework sources, arXiv, analyst writing, and curated learning repositories are underrepresented.

GitHub selection currently treats broad static popularity and recent push activity as quality. This can miss repositories that are highly relevant and currently trending, such as `datawhalechina/Agent-Learning-Hub`, while still admitting weak-fit repositories that happen to match broad keywords or pass a low popularity bar.

The star policy is especially fragile because total stars, recent pushes, and current learning value are different signals. A mature repository with many total stars may be old news; a small repository with only a few stars may be noise; and a repository gaining thousands of stars during the past week is a strong discovery signal even if it is not captured by a broad static query.

Relevance scoring is too generic. The system asks whether an item is related to AI, LLMs, or agents, but not whether it belongs inside the owner’s actual interest boundary. The goal is not to suppress everything uncertain; the goal is to avoid missing genuinely relevant signals.

Ranking is not discriminative enough. Too many items receive similar scores, so the score does not produce a real reading queue or study priority.

Tags are too flat. Tags such as `llm`, `agent`, or `evaluation` describe broad domains, but they do not capture why an item matters: tutorial value, architecture reference, implementation pattern, production lesson, research method, or background context.

Summaries are item-level, not knowledge-building-level. They usually explain what the item is, but do not consistently answer:

- Why should I study this?
- What capability does it build?
- What should I do next?
- Is this a deep-read, skim, archive, or skip?

The organizer behaves like an archive, not a relevance-aware intelligence layer. It stores items but does not clearly separate captured coverage, ranked priority, learning candidates, background context, and low-confidence items.

The system has limited feedback memory. If low-value content keeps entering the corpus, the filtering policy does not clearly learn from those decisions.

## Strategy

Define a personal relevance policy with three priority tiers. These tiers should guide ranking and presentation, not hard deletion. Recall matters: borderline but plausibly relevant items should be preserved with lower priority and clear reasons.

**P0 Must Learn** should include agent harnesses, LangGraph and LangChain workflows, tool-use systems, MCP, browser/computer-use agents, data agents, production evaluation, applied RAG, and repositories with tutorial depth or reference architecture value.

**P1 Valuable Context** should include LLM engineering, fine-tuning practice, model serving, local model workflows, AI coding systems, applied ML/RL, quantitative and data workflows, and AI product or business implications.

**P2 Background Or Low Priority** should include generic AI discourse, hiring or conference administration, hype without technical content, broad enterprise AI commentary, shallow demos, and narrow niche ML papers only weakly related to the roadmap. These items should usually be skimmed or deprioritized, but not automatically discarded if they may contain useful signal.

Create a source portfolio policy:

- Maintain a seed list of must-watch repositories and organizations, including `datawhalechina/Agent-Learning-Hub`.
- Separate sources by role: must-watch repositories, official and framework sources, research feeds, engineering blogs, community discovery, and background news.
- Give each role a quota so community feeds can surface surprises without dominating the library.
- Treat GitHub stars as multiple separate signals, not one generic popularity number: total stars, recent star growth, trending rank, topic match, documentation quality, ecosystem importance, and hands-on usefulness.
- Give seed repositories and high star-velocity repositories explicit coverage priority, even when they are not surfaced by the broad GitHub search query.
- Penalize low-star repositories unless they have a clear reason to be captured: exact topic match, trusted author/org, strong tutorial value, reference architecture value, or unusual novelty.
- Distinguish "recently pushed" from "currently trending." A push means activity; star velocity means market/learning attention.

Create a relevance ranking policy:

- Score every candidate on personal fit, technical depth, actionability, source credibility, and novelty.
- For GitHub repositories, include a dedicated discovery score that separates must-watch status, recent star velocity, total stars, topic fit, and repo usefulness.
- Penalize generic discussion, missing technical artifacts, unclear learning payoff, hype framing, duplicated themes, and irrelevant domains.
- Assign each candidate a reading priority: `study-now`, `save-for-context`, `skim`, `low-priority`, or `skip`.
- Treat `skip` as reserved for clearly irrelevant, duplicate, broken, or low-quality items. Uncertain but possibly relevant items should remain captured as low-priority.
- Preserve low-priority and skip reasons as feedback, not just deletion.

Create a tagging policy:

- Keep broad domain tags, but add learning-intent tags such as `agent-harness`, `langgraph`, `data-agent`, `mcp`, `tool-use`, `evaluation`, `repo-tutorial`, `reference-architecture`, `paper-to-code`, `production-rag`, `local-llm`, `quant-ai`, `business-context`, and `noise`.
- Require each saved item to answer two questions: what area does this belong to, and why does it matter to me?
- Track source type separately from topic: repository, paper, blog, discussion, benchmark, tutorial, product, or news.

Create a summarization policy:

- Every summary should include the core idea, technical mechanism, personal learning value, suggested learning action, and confidence.
- GitHub repository summaries should emphasize what to learn, maturity, documentation quality, architecture value, and whether the repo deserves clone-and-study treatment.
- Paper summaries should emphasize the problem, method, practical relevance, implementation difficulty, and connection to agent, data, or ML work.
- Discussion and news summaries should be saved only when they change judgment, reveal practice patterns, or expose meaningful risks.

Create a knowledge-building policy:

- Cluster items into learning tracks: Agent Systems, LangGraph Workflows, Data Agents, RAG and Knowledge Systems, Evaluation, Local Model Serving, ML/RL Foundations, Quant and Data Science, and Engineering Leadership.
- Promote repeated high-signal themes into synthesis notes or knowledge cards.
- Demote stale or low-signal items in presentation while preserving them when they remain plausibly relevant.
- Produce a weekly review output with top study items, context items, low-priority captures, skipped patterns, and source coverage gaps.

## Acceptance Criteria

- `datawhalechina/Agent-Learning-Hub` and similar seed repositories are always considered, regardless of generic GitHub popularity.
- Repositories with strong recent star growth in relevant topics are captured or at least surfaced for review, even if they are missed by static star-sorted search.
- Low-star repositories are not promoted unless they have explicit relevance evidence.
- Community discussion items no longer dominate the published corpus.
- A daily run captures broadly within the owner’s relevance boundary and produces a useful ranked reading queue, not just a list of saved articles.
- Scores spread meaningfully across low, medium, and high priority.
- Each saved item has a clear reason explaining why it matters to the owner’s learning goals.
- Tags support retrieval by learning goal, not only by broad AI topic.
- The system can explain why an item was promoted for study, saved for context, kept as low-priority, downgraded, or skipped.

## Assumptions

- The primary objective is coverage plus relevance: capture news and technical signals genuinely related to the owner, then let a human choose what to learn.
- Recall is important. The system should avoid over-filtering plausible matches, especially in agent engineering, data agents, AI development workflow, ML/RL, quantitative analysis, and applied engineering.
- Precision should come from ranking, tagging, and explanation, not from aggressively deleting uncertain items.
- Repositories, tutorials, reference architectures, and applied engineering writeups should outrank generic news.
- This document is a strategy plan, not an OpenSpec change.
- The plan intentionally avoids implementation details and code-level recommendations.
