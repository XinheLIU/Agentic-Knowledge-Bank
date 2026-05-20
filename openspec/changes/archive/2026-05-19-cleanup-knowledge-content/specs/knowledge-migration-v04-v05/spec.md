## ADDED Requirements

### Requirement: 一次性迁移脚本
`scripts/migrate_v04_to_v05.py` SHALL 将 `knowledge/articles/` 中所有 v0.4 schema 的条目（`status=review` 且缺 `key_insight` 等字段）就地升级为 v0.5 schema。

#### Scenario: dry-run 模式只打印不写入
- **WHEN** 以 `--dry-run` 运行脚本
- **THEN** 脚本 SHALL 打印将改动的文件列表与字段差异，SHALL NOT 修改文件系统

#### Scenario: 正常运行迁移所有旧条目
- **WHEN** 不带 `--dry-run` 运行脚本
- **THEN** 所有原 v0.4 条目 SHALL 含 `key_insight`、`category`（单值）、`relevance_score`，且 `status` SHALL 不再是 `review`（除非 analyzer 重跑后 reviewer 仍判待审）

### Requirement: 迁移可重入
脚本 SHALL 可重复运行而不破坏已迁移条目。已是 v0.5 的条目 SHALL 被跳过。

#### Scenario: 重复运行幂等
- **WHEN** 在已成功迁移后再次运行脚本
- **THEN** 脚本 SHALL 报告 0 个待迁移条目并以 0 退出码退出

### Requirement: 文件重命名到新格式
迁移过程中 SHALL 将旧文件名（如 `rss-20260502-001.json` 或 `rss:reddit-r-machinelearning-20260507-001.json`）改名为 `<source-slug>-<YYYYMMDD>-<NNN>.json`。

#### Scenario: 旧 rss-NNN 改名
- **WHEN** 一个旧条目文件名为 `rss-20260502-001.json` 且其内容指向 reddit r/MachineLearning
- **THEN** 文件 SHALL 被改名为 `reddit-ml-20260502-<NNN>.json`，其中 NNN 在该 (slug, date) 下避免冲突

#### Scenario: 含冒号文件名改名
- **WHEN** 一个文件名含冒号
- **THEN** 改名后的文件名 SHALL 不含冒号且符合新正则

### Requirement: published_at 与 author 反查 raw/
对于在 `knowledge/raw/` 中能找到对应原始抓取的旧条目，迁移脚本 SHALL 从 raw 反查并回填 `published_at` 与 `author`；找不到时 SHALL 显式写 `null`。

#### Scenario: raw 命中
- **WHEN** 旧条目 `source_url` 在 raw 中可匹配且 raw 含发布时间
- **THEN** `published_at` SHALL 被回填为 raw 中的值

#### Scenario: raw 未命中
- **WHEN** 旧条目无对应 raw
- **THEN** `published_at` 与 `author` SHALL 被置为 `null`，且 `collected_at` 保持原值

### Requirement: 迁移后重建 index
脚本运行结束时 SHALL 调用 `scripts/build_index.py` 全量重建 `index.json`。

#### Scenario: 迁移结束 index 与 FS 一致
- **WHEN** 迁移脚本运行完成
- **THEN** `index.json` 的条目数 SHALL 等于 `knowledge/articles/*.json` 文件数
