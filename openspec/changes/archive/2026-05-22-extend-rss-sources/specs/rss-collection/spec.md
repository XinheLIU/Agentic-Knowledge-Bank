## ADDED Requirements

### Requirement: Per-Source Quota Configuration

RSS sources SHALL support a `per_source_limit` integer field in `rss_sources.yaml` declaring the maximum number of items to take from that source in one collection run. The field SHALL default to 5 when omitted.

#### Scenario: Source with explicit per_source_limit
- **WHEN** `rss_sources.yaml` contains a source with `per_source_limit: 3`
- **THEN** `collect_rss` SHALL take at most 3 items from that source's feed

#### Scenario: Source without per_source_limit
- **WHEN** a source entry omits `per_source_limit`
- **THEN** `collect_rss` SHALL treat its limit as 5

#### Scenario: Backward compatibility with old yaml
- **WHEN** loading an existing yaml that has no `per_source_limit` on any source
- **THEN** `collect_rss` SHALL succeed without error and apply the default of 5 to each source

### Requirement: Proportional Quota Scaling

When the sum of all enabled sources' `per_source_limit` values exceeds the global cap passed by the planner, `collect_rss` SHALL scale each source's actual quota proportionally, never reducing any source below 1 item.

#### Scenario: Total quota within global cap
- **WHEN** enabled sources have per_source_limits summing to 50 and global cap is 100
- **THEN** each source's actual quota equals its `per_source_limit`

#### Scenario: Total quota exceeds global cap
- **WHEN** enabled sources have per_source_limits summing to 100 and global cap is 50
- **THEN** each source's actual quota equals `max(1, ceil(per_source_limit * 50 / 100))`

#### Scenario: Tiny source preserved under aggressive scaling
- **WHEN** a source has `per_source_limit: 3` and the scaling factor would compute to 0.1
- **THEN** that source's actual quota SHALL be 1, not 0

### Requirement: Cross-Source Content Fingerprint Deduplication

After collecting items from all sources in a run, `collect_rss` SHALL deduplicate items by a fingerprint computed from the title and URL domain, and SHALL also drop items whose fingerprint matches any article already persisted under `knowledge/articles/`.

The fingerprint formula SHALL be:
- Lowercase the title and remove all characters except letters, digits, and CJK ideographs
- Concatenate with `|` and the URL's lowercased netloc with the `www.` prefix stripped

#### Scenario: Same article from two different sources
- **WHEN** two items have the same domain and titles `"GPT-5 is here!"` and `"GPT 5 is here"`
- **THEN** only one item is kept after dedupe

#### Scenario: Same title from different domains
- **WHEN** two items have title `"Claude 4 released"` but URLs at `anthropic.com` and `news.ycombinator.com`
- **THEN** both items are kept (different fingerprints)

#### Scenario: Article already persisted
- **WHEN** `knowledge/articles/` contains an article whose fingerprint equals a freshly-collected item's fingerprint
- **THEN** the freshly-collected item SHALL be dropped before being returned

### Requirement: New RSS Source Catalog

`rss_sources.yaml` SHALL include 18 new RSS sources in addition to the existing 12, covering official labs, AI analysts, engineering blogs, and news aggregators. The previously-disabled `arxiv-cs-cl` source SHALL be set to `enabled: true`.

#### Scenario: New sources are reachable and parseable
- **WHEN** `collect_rss` runs with all new sources enabled
- **THEN** each of the 18 new source URLs returns HTTP 200 and parses as a valid RSS or Atom feed without raising

#### Scenario: arxiv-cs-cl is enabled
- **WHEN** loading the new `rss_sources.yaml`
- **THEN** the `arxiv-cs-cl` source has `enabled: true` (or no `enabled` key, defaulting to true)

### Requirement: Reduced Per-Request Timeout

`collect_rss` SHALL use an HTTP timeout of at most 10 seconds per source and a connect timeout of at most 5 seconds, to bound worst-case run time when many sources are configured.

#### Scenario: Slow source does not block run beyond timeout
- **WHEN** one source's server takes 30 seconds to respond
- **THEN** `collect_rss` aborts that source's fetch at 10 seconds and continues to the next source
