## ADDED Requirements

### Requirement: 单一文章 JSON Schema
系统 SHALL 在 `knowledge/articles/` 下只接受 v0.5 schema 的文章 JSON，包含字段：`id`、`source`、`source_url`、`url`、`title`、`author`、`published_at`、`collected_at`、`summary`、`key_insight`、`category`、`tags`、`audience`、`score`、`relevance_score`、`status`。

#### Scenario: v0.5 条目写入成功
- **WHEN** 一个包含全部 v0.5 字段的 JSON 写入 `knowledge/articles/`
- **THEN** `scripts/validate_json.py` SHALL 校验通过

#### Scenario: 缺失 v0.5 必填字段被拒绝
- **WHEN** 一个 JSON 缺少 `key_insight` 或 `category` 或 `relevance_score`
- **THEN** `scripts/validate_json.py` SHALL 返回非 0 退出码并打印缺失字段

### Requirement: 文件名与 ID 格式收敛
系统 SHALL 强制文件名格式 `<source-slug>-<YYYYMMDD>-<NNN>.json`，其中 `source-slug` 匹配 `^[a-z0-9-]+$`，`NNN` 为 3 位零填充序号。文件名 SHALL NOT 包含冒号、空格、大写字母。

#### Scenario: 合法文件名通过校验
- **WHEN** 文件名为 `reddit-ml-20260507-001.json`
- **THEN** validator SHALL 通过

#### Scenario: 含冒号的文件名被拒绝
- **WHEN** 文件名为 `rss:reddit-r-machinelearning-20260507-001.json`
- **THEN** validator SHALL 失败并提示禁止冒号

### Requirement: source slug 来自配置
`workflows/rss_sources.yaml` 中每个源 SHALL 包含 `slug` 字段（kebab-case），collector 在生成文件名时 SHALL 使用该 slug，而非源 `name`。

#### Scenario: 配置缺 slug 时阻止采集
- **WHEN** `rss_sources.yaml` 某个源缺 `slug` 字段且 collector 试图为该源生成文件
- **THEN** collector SHALL 报错退出而非用 `name` 推断
