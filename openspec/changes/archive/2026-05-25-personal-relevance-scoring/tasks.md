## 1. Configurable relevance profile

- [x] 1.1 Add `workflows/relevance_profile.yaml` with the default profile derived from `docs/personal-knowledge-strategy-plan.md`.
- [x] 1.2 Add a small profile loader that reads user status, focus topics, learning tracks, source type preferences, priority bands, learning tag allowlist, and negative patterns.
- [x] 1.3 Make missing or partial profile config recoverable by falling back to safe defaults.
- [x] 1.4 Add non-LLM tests for profile loading, default fallback, and partial config handling.

## 2. Analyzer personal relevance output

- [x] 2.1 Expand analyzer tag allowlists to include broad tags and learning-intent tags separately.
- [x] 2.2 Update analyzer prompt to inject the active relevance profile instead of hard-coding the owner's roadmap in Python.
- [x] 2.3 Require analyzer JSON to include component scores, `priority_score`, `reading_priority`, `relevance_reason`, `suggested_action`, `confidence`, `source_type`, `learning_track`, and `learning_tags`.
- [x] 2.4 Normalize/clamp component scores to `0.0..1.0`, `priority_score` to `0..100`, `score` to `1..10`, and priority enum values to the allowed set.
- [x] 2.5 Preserve `relevance_score` as personal fit compatibility output.
- [x] 2.6 Add non-LLM tests for analyzer normalization of new fields and prompt use of the active profile.

## 3. Organizer persistence

- [x] 3.1 Persist the new ranking/tagging fields into article JSON.
- [x] 3.2 Provide safe defaults for missing fields so fallback or partial LLM output still produces valid reviewable articles.
- [x] 3.3 Ensure existing required fields remain unchanged for compatibility.
- [x] 3.4 Add tests that `build_articles()` preserves `learning_tags`, `reading_priority`, `priority_score`, `source_type`, and `learning_track`.

## 4. Validation and quality scoring

- [x] 4.1 Extend `hooks/validate_json.py` to validate optional new enum/range fields when present.
- [x] 4.2 Extend quality tag allowlists so learning-intent tags are not treated as invalid noise.
- [x] 4.3 Update `hooks/check_quality.py` dimensions to reward personal relevance, actionability, valid learning tags, source type, and learning track.
- [x] 4.4 Keep existing articles valid; new validation must not require new fields for historical JSON files.
- [x] 4.5 Add hook tests for high-personal-fit article, generic low-priority article, and learning tag validation.

## 5. Reviewer alignment

- [x] 5.1 Update reviewer prompt semantics from generic AI relevance to active relevance profile compliance.
- [x] 5.2 Ensure reviewer feedback calls out weak personal fit, unclear learning payoff, missing technical mechanism, or invalid priority assignment.
- [x] 5.3 Keep reviewer behavior batch-compatible; do not redesign the workflow graph in this change.
- [x] 5.4 Add/update tests for reviewer score dimensions or prompt expectations where practical.

## 6. Verification and documentation

- [x] 6.1 Run `uv run pytest -q -m non_llm`.
- [x] 6.2 Run targeted hook validation/quality tests against fixtures.
- [x] 6.3 Run a dry-run workflow with RSS or GitHub and inspect score spread without writing production articles.
- [x] 6.4 Update `AGENTS.md` to document the relevance profile config, new article fields, scoring semantics, and tagging policy; update its Last updated date.
