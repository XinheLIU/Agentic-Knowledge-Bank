# Context

> Last updated: 2026-10-04

Canonical terminology for the AI 知识库 (AI Knowledge Base) project. Source of truth for vocabulary that must stay consistent across the admission pipeline and personal-relevance policy. Extracted from `AGENTS.md`.

## Focus topics (三级优先主题)

Configured in the Horizon profile `ai-kb-personal/` shipped with Information Assistant (`information_assistant/resources/horizon-profiles/ai-kb-personal/`; formerly `workflows/relevance_profile.yaml`, retired with the legacy pipeline in ticket 16), ordered by priority:

- **P0 必学** — must-learn topics, highest weight.
- **P1 有价值上下文** — valuable context.
- **P2 背景** — background awareness.

## Learning tracks (学习路线)

The `learning_track` field assigns each article to one learning route defined in the relevance profile. Values come from the profile's `learning_tracks` mapping.

## Reading priority (阅读优先级)

The `reading_priority` enum, in descending order:

| Value | Meaning |
|---|---|
| `study-now` | Study immediately |
| `save-for-context` | Save for context |
| `skim` | Skim |
| `low-priority` | Low priority |
| `skip` | Skip — reserved for clearly irrelevant, duplicate, broken, or low-quality items |

Rule caps: discussion/news without a technical mechanism cap at `low-priority`; a P0 match with tutorial/reference value floors at `save-for-context`; uncertain items use `low-priority` rather than `skip`.

## Learning tags allowlist (学习标签)

`learning_tags` draws only from this closed allowlist (21 tags):

`agent-harness`, `langgraph`, `langchain`, `data-agent`, `mcp`, `tool-use`, `browser-agent`, `computer-use`, `evaluation`, `repo-tutorial`, `reference-architecture`, `paper-to-code`, `production-rag`, `local-llm`, `quant-ai`, `business-context`, `implementation-pattern`, `architecture-reference`, `production-lesson`, `research-method`, `noise`

## Source types (来源类型)

The `source_type` enum: `repository`, `paper`, `blog`, `discussion`, `benchmark`, `tutorial`, `product`, `news`, `documentation`, `unknown`.

## Negative patterns (噪音模式)

Configured in the Horizon profile `ai-kb-personal/` (owned by Information Assistant) and enforced as executable negative patterns in `kb/admission/patterns.py`. These are noise patterns that lower or reject a candidate's relevance.

## Horizon cutover vocabulary

| Term | Meaning |
|---|---|
| Horizon radar | The upstream system that fetches, scores, and enriches candidate information. It does not own this project's durable knowledge model. |
| Knowledge asset | An admitted, durable item available to retrieval and downstream consumption. A fetched candidate is not yet a knowledge asset. |
| Admission decision | The per-item, explainable outcome that accepts or rejects a candidate under a versioned personal policy. |
| Ingestion run | One auditable attempt that accounts for every candidate as accepted, rejected, or failed. |

## Scoring vocabulary

| Field | Meaning |
|---|---|
| `personal_fit_score` | Match to the user's learning tracks (0.0–1.0) |
| `technical_depth_score` | Technical depth (0.0–1.0) |
| `actionability_score` | Learning/action value (0.0–1.0) |
| `source_credibility_score` | Source credibility (0.0–1.0) |
| `novelty_score` | Novelty (0.0–1.0) |
| `priority_score` | Weighted composite priority (0–100) |
| `confidence` | Scoring confidence (0.0–1.0) |
| `relevance_score` | Compatibility field; mirrors `personal_fit_score` |
| `score` | Compatibility field (1–10); derived from `priority_score` |

## Quality grades

Six dimensions, 115 points total: summary (25), technical depth (25), format (20), tag precision (15, split broad + learning), hollow-word detection (15), personal relevance (15). Grades: A (≥90), B (≥70), C (<70).

## Broad tags

`tags` is the open-ended broad tag field (English, lowercase, prefer quality-script-recognized tags). Distinct from the closed `learning_tags` allowlist.
