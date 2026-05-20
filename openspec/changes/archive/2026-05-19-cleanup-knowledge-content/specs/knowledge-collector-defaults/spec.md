## ADDED Requirements

### Requirement: 缺失发布时间写 null
Collector SHALL 把 feed entry 的发布时间解析为 `published_at`，解析失败或字段缺失时 SHALL 写 `null`，SHALL NOT 用 `collected_at` 作为 fallback。

#### Scenario: feed 含 pubDate 时正常解析
- **WHEN** entry 包含合法 `pubDate`
- **THEN** `published_at` SHALL 为该时间的 ISO 8601 字符串

#### Scenario: feed 无 pubDate 时为 null
- **WHEN** entry 缺 `pubDate` 字段
- **THEN** `published_at` SHALL 为 `null`，且 `collected_at` SHALL 仍为当前采集时间

### Requirement: 缺失作者写 null
Collector SHALL 在 feed entry 的 `author` 字段缺失时写 `null`，SHALL NOT 用源 `name` 作为 fallback。

#### Scenario: entry 含 author 时保留
- **WHEN** entry 包含 `author: "Jane Doe"`
- **THEN** JSON 中 `author` SHALL 为 `"Jane Doe"`

#### Scenario: entry 无 author 时为 null
- **WHEN** entry 缺 `author`
- **THEN** JSON 中 `author` SHALL 为 `null`，源信息只通过 `source` 字段表达
