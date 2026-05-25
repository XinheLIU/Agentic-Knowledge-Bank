## Why

> Last updated: 2026-05-24

The knowledge base currently ranks items by generic AI/LLM/Agent relevance and a loosely defined `score`. This makes the published corpus useful as an archive, but weak as a personal technical intelligence system: generic discussion can look as important as a LangGraph tutorial repo, while high-value learning material may be dropped or flattened into the same score band.

The strategy in `docs/personal-knowledge-strategy-plan.md` calls for coverage plus personal relevance: preserve plausible signals, rank them by the owner's learning roadmap, and explain why each item matters. This change focuses only on scoring, tagging, and persistence. Source portfolio, seed repositories, GitHub star velocity, and weekly review outputs are intentionally left for later changes.

## What Changes

- Redefine analyzer relevance around a configurable user relevance profile, not generic AI topic fit or a hard-coded roadmap.
- Add a user-editable relevance configuration describing the user's current status, focus topics, priority tiers, learning tracks, preferred source types, and negative/noise patterns.
- Add per-item personal intelligence fields: `personal_fit_score`, `technical_depth_score`, `actionability_score`, `source_credibility_score`, `novelty_score`, `priority_score`, `reading_priority`, `relevance_reason`, `suggested_action`, `confidence`, `source_type`, `learning_track`, and `learning_tags`.
- Preserve existing compatibility fields where practical: `relevance_score` remains present and mirrors personal fit semantics; `score` remains a 1-10 compatibility ranking derived from priority.
- Expand tag validation/scoring so learning-intent tags are treated as valid quality signals instead of invalid noise.
- Adjust quality scoring to evaluate personal relevance and learning utility rather than only summary length, broad tags, and overloaded `score`.
- Keep skip behavior conservative: `skip` is reserved for clearly irrelevant, duplicate, broken, or low-quality items; uncertain but plausible items should be captured with low priority.

## Capabilities

### New Capabilities
- `knowledge-ranking`: personal relevance scoring, reading priority assignment, learning-intent tags, and quality scoring semantics for stored knowledge articles.

### Modified Capabilities
- `knowledge-analyzer-output`: analyzer output schema is extended with personal scoring and tagging fields while preserving existing required fields.

## Impact

- **Code**:
  - `workflows/relevance_profile.yaml`: default configurable relevance profile based on the strategy plan.
  - `workflows/analyzer.py`: load relevance profile, prompt construction, output parsing, tag normalization, priority/score compatibility.
  - `workflows/organizer.py`: persistence of new fields and defaults for compatibility.
  - `hooks/validate_json.py`: optional enum validation for new ranking/tagging fields.
  - `hooks/check_quality.py`: quality dimensions updated to reward personal relevance, learning intent, and actionable summaries.
  - `tests/`: add focused non-LLM tests for analyzer parsing, organizer persistence, validation, and quality scoring.
- **Data**:
  - Existing articles remain valid.
  - New articles include additional fields for learning-oriented retrieval and ranking.
- **Dependencies**: no new dependencies.
- **Out of scope**:
  - Must-watch repository seed lists.
  - GitHub star velocity or trending collection.
  - Source portfolio quotas beyond existing RSS quotas.
  - Weekly review generation or UI reading queue changes.
