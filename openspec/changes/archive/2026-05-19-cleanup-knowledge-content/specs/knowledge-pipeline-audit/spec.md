## ADDED Requirements

### Requirement: 淘汰条目写入 _skipped.jsonl
系统 SHALL 在 `knowledge/articles/_skipped.jsonl` 以一行一条 JSON 的形式记录所有被 analyzer/reviewer/organizer 淘汰的条目，每行至少包含 `id`、`source`、`source_url`、`stage`、`reason`、`ts` 字段。

#### Scenario: analyzer 因 relevance_score 低淘汰
- **WHEN** analyzer 判定某条 `relevance_score < threshold`
- **THEN** `_skipped.jsonl` SHALL 追加一行，`stage` 字段为 `"analyzer"`，`reason` 含分数信息

#### Scenario: reviewer 否决
- **WHEN** reviewer 节点返回否决
- **THEN** `_skipped.jsonl` SHALL 追加一行，`stage` 为 `"reviewer"`

#### Scenario: organizer 校验失败
- **WHEN** organizer 校验 schema 失败且无法降级修复
- **THEN** `_skipped.jsonl` SHALL 追加一行，`stage` 为 `"organizer"`

### Requirement: 编号空间与 articles 共享
被淘汰条目占用的 `id` SHALL 不被 collector 重复分配给后续新条目。collector 分配新编号时 SHALL 扫描 articles/ 与 `_skipped.jsonl` 已用 id 的并集。

#### Scenario: 同 (source, date) 下不撞号
- **WHEN** `_skipped.jsonl` 含 id `reddit-ml-20260503-005` 且 collector 当天为 reddit-ml 分配新编号
- **THEN** 新条目 id SHALL 不为 `005`
