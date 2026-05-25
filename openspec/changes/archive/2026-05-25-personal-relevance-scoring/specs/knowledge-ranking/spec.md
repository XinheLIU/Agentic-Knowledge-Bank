## ADDED Requirements

### Requirement: Relevance policy is configurable

The system SHALL score personal relevance from an active user relevance profile rather than hard-coded Python prompt text.

#### Scenario: Default profile is available
- **WHEN** the analyzer runs without a user-provided profile override
- **THEN** it SHALL use a checked-in default relevance profile
- **AND** the profile SHALL include user status, focus topics, learning tracks, preferred source types, and negative patterns

#### Scenario: User status influences scoring context
- **WHEN** the profile describes the user's current status or learning stage
- **THEN** analyzer relevance scoring SHALL consider that status when assigning `personal_fit_score`, `reading_priority`, and `suggested_action`

#### Scenario: Focus topics influence personal fit
- **WHEN** the profile lists focus topics such as agent engineering, data agents, RAG, evaluation, or quantitative analysis
- **THEN** matching items SHALL receive higher personal fit than generic AI items with no focus-topic match, all else equal

#### Scenario: Profile fallback is safe
- **WHEN** the relevance profile is missing or partially specified
- **THEN** the analyzer SHALL fall back to conservative defaults
- **AND** the workflow SHALL continue without failing solely because optional profile fields are absent

### Requirement: Articles carry personal relevance scoring

Newly organized knowledge articles SHALL preserve personal relevance scoring fields in addition to existing compatibility fields.

#### Scenario: High-fit article includes component scores
- **WHEN** an analyzed item is organized into an article
- **THEN** the article SHALL include `personal_fit_score`, `technical_depth_score`, `actionability_score`, `source_credibility_score`, `novelty_score`, and `priority_score`
- **AND** component scores SHALL be numeric values between `0.0` and `1.0`
- **AND** `priority_score` SHALL be a numeric value between `0` and `100`

#### Scenario: Existing compatibility fields remain present
- **WHEN** an article is written
- **THEN** it SHALL still include `relevance_score` and `score`
- **AND** `relevance_score` SHALL represent fit against the active relevance profile
- **AND** `score` SHALL remain a numeric value from `1` to `10`

### Requirement: Articles carry reading priority

Newly organized knowledge articles SHALL include a reading priority that turns scoring into a human study queue.

#### Scenario: Valid reading priority is stored
- **WHEN** an article is written
- **THEN** it SHALL include `reading_priority`
- **AND** `reading_priority` SHALL be one of `study-now`, `save-for-context`, `skim`, `low-priority`, or `skip`

#### Scenario: Uncertain but plausible item is not skipped
- **WHEN** an item has plausible personal relevance but low confidence
- **THEN** it SHALL be assigned `low-priority` rather than `skip`
- **AND** the article SHALL include a `relevance_reason` explaining the uncertainty

#### Scenario: Skip is reserved for clear rejection cases
- **WHEN** an item is clearly irrelevant, duplicate, broken, empty, or low-quality
- **THEN** it MAY be assigned `skip`
- **AND** the reason SHALL be preserved in `relevance_reason` or skipped-item feedback

### Requirement: Articles explain why they matter

Newly organized knowledge articles SHALL explain personal learning value, not only summarize the source item.

#### Scenario: Relevance reason is stored
- **WHEN** an article is written
- **THEN** it SHALL include non-empty `relevance_reason`
- **AND** the reason SHALL explain why the item matters or does not matter to the owner’s learning roadmap

#### Scenario: Suggested learning action is stored
- **WHEN** an article is written
- **THEN** it SHALL include `suggested_action`
- **AND** the value SHALL indicate the next action, such as clone-and-study, deep-read, skim, archive, or skip

#### Scenario: Confidence is stored
- **WHEN** an article is written
- **THEN** it SHALL include `confidence`
- **AND** `confidence` SHALL be a numeric value between `0.0` and `1.0`

### Requirement: Articles separate source type from topic

Newly organized knowledge articles SHALL preserve source type separately from transport source and broad topic category.

#### Scenario: Source type is stored
- **WHEN** an article is written
- **THEN** it SHALL include `source_type`
- **AND** `source_type` SHALL be one of `repository`, `paper`, `blog`, `discussion`, `benchmark`, `tutorial`, `product`, `news`, `documentation`, or `unknown`

#### Scenario: Learning track is stored
- **WHEN** an article is written
- **THEN** it SHALL include `learning_track`
- **AND** `learning_track` SHALL be one of `agent-systems`, `langgraph-workflows`, `data-agents`, `rag-knowledge-systems`, `evaluation`, `local-model-serving`, `ml-rl-foundations`, `quant-data-science`, `engineering-leadership`, `business-context`, or `background`

### Requirement: Articles support learning-intent tags

Newly organized knowledge articles SHALL support learning-intent tags separately from broad domain tags.

#### Scenario: Learning tags are stored
- **WHEN** analyzer identifies why an item matters to the owner
- **THEN** organizer SHALL store those labels in `learning_tags`
- **AND** `learning_tags` SHALL be a list of lowercase strings

#### Scenario: Learning tags do not invalidate quality scoring
- **WHEN** an article includes learning tags such as `langgraph`, `agent-harness`, `repo-tutorial`, or `reference-architecture`
- **THEN** quality scoring SHALL treat those tags as valid learning-intent tags
- **AND** SHALL NOT penalize the article merely because those tags are not broad domain tags

### Requirement: Quality scoring reflects personal intelligence value

The article quality hook SHALL evaluate alignment with the personal knowledge policy, not only generic article polish.

#### Scenario: Generic polished content is not over-rewarded
- **WHEN** an article has a long summary but low personal fit, weak technical mechanism, and no actionable learning value
- **THEN** quality scoring SHALL not classify it as high quality solely because the summary is long and formatted correctly

#### Scenario: Personal learning fields improve quality score
- **WHEN** an article includes valid component scores, reading priority, relevance reason, suggested action, source type, learning track, and valid learning tags
- **THEN** quality scoring SHALL reward those fields as quality evidence

#### Scenario: Historical articles remain valid
- **WHEN** an existing article lacks the new personal relevance fields
- **THEN** JSON validation SHALL NOT fail solely because those new fields are absent
- **AND** quality scoring MAY assign lower quality for missing personal intelligence fields
