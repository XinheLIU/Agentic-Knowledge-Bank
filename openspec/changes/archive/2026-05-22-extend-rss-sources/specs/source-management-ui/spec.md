## ADDED Requirements

### Requirement: List All Configured Sources

The UI SHALL expose `GET /api/sources` returning a JSON array of all sources defined in `rss_sources.yaml`, each enriched with the count of articles collected from that source in the last 7 days.

Each array element SHALL contain at minimum: `slug`, `name` (if present), `url`, `category`, `per_source_limit`, `enabled`, and `last_7d_count` (integer).

#### Scenario: Fetch source list
- **WHEN** the client sends `GET /api/sources`
- **THEN** the response is HTTP 200 with a JSON array of source objects, one per source in the yaml

#### Scenario: Article count reflects recent activity
- **WHEN** `knowledge/articles/` contains 3 articles from `simonwillison` with `collected_at` within the last 7 days and 10 older articles from the same source
- **THEN** the `simonwillison` entry returned by `GET /api/sources` has `last_7d_count: 3`

### Requirement: Toggle Source Enabled State

The UI SHALL expose `PATCH /api/sources/<slug>` accepting a JSON body `{"enabled": <bool>}` that updates the `enabled` field of the matching source in `rss_sources.yaml` and persists the change atomically.

#### Scenario: Disable an enabled source
- **WHEN** the client sends `PATCH /api/sources/hn-best` with body `{"enabled": false}`
- **THEN** the response is HTTP 200 and `rss_sources.yaml` is updated so `hn-best` has `enabled: false`

#### Scenario: Unknown slug
- **WHEN** the client sends `PATCH /api/sources/does-not-exist` with body `{"enabled": true}`
- **THEN** the response is HTTP 404 and `rss_sources.yaml` is unchanged

#### Scenario: Atomic write prevents partial file
- **WHEN** the write process is interrupted (e.g. disk full) mid-write
- **THEN** `rss_sources.yaml` retains its previous valid content rather than being truncated

### Requirement: Source Management View in SPA

The UI SPA SHALL provide a source management view showing every source as a table row with its slug, category, `last_7d_count`, and a toggle control that calls `PATCH /api/sources/<slug>` when flipped.

#### Scenario: User toggles a source off in the UI
- **WHEN** the user flips the toggle for `hn-best` from on to off
- **THEN** the front end sends `PATCH /api/sources/hn-best` with `{"enabled": false}` and the toggle stays off after the page is reloaded

#### Scenario: Source list reflects recent activity
- **WHEN** the user opens the source management view
- **THEN** each row's `last_7d_count` column shows the number returned by `GET /api/sources`
