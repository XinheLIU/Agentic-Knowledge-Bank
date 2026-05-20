## ADDED Requirements

### Requirement: index.json 是派生产物
`knowledge/articles/index.json` SHALL 由 `scripts/build_index.py` 全量扫描 `knowledge/articles/*.json` 生成，pipeline 运行末尾调用一次。任何节点 SHALL NOT 增量写入 index。

#### Scenario: pipeline 结束后 index 与 FS 一致
- **WHEN** 一次 pipeline 运行结束
- **THEN** `index.json` 条目数 SHALL 等于 `knowledge/articles/*.json`（不含 `_skipped.jsonl` 与 `index.json` 自身）的文件数

#### Scenario: 单条文章被手工删除后重建 index
- **WHEN** 手工删除 `knowledge/articles/<id>.json` 后运行 `scripts/build_index.py`
- **THEN** `index.json` SHALL NOT 再包含该 id

### Requirement: organizer 不写 index
`workflows/organizer.py` SHALL NOT 包含任何对 `index.json` 的写入或追加逻辑。

#### Scenario: 单元测试断言 organizer 无 index 写入
- **WHEN** mock 文件系统并跑一次 organizer 节点
- **THEN** `index.json` 路径上 SHALL NOT 发生写操作
