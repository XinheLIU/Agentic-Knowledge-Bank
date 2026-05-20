# Knowledge Content Cleanup Report

> Last updated: 2026-05-19

## 变更摘要

本次变更一次性将 `knowledge/articles/` 下所有 213 条条目收敛到 v0.5 schema，消除了双代共存、index 漂移、文件名规则不统一、占位符字段污染、分类多值化、淘汰条目静默丢失等问题。

## 迁移前后数字对比

| 指标 | 迁移前 | 迁移后 |
|------|--------|--------|
| 总条目数 | 213 | 213 |
| v0.4 schema（缺 key_insight/category/relevance_score/url） | 73 | 0 |
| v0.5 schema | 140 | 213 |
| 含冒号的 ID / 文件名 | 136 | 0 |
| index.json 与文件系统一致 | ❌（只索引 67 条） | ✅（213 条） |
| 全量通过 validate_json.py | ❌（211 失败） | ✅（213/213 通过） |
| category 全部单值且在枚举内 | ❌（含多值字符串） | ✅ |
| author 为源名 fallback | 大量 | 0（已置 null） |
| published_at 为 collected_at fallback | 大量 | 0（已置 null） |
| _skipped.jsonl 审计记录 | 无 | 3 条 |

## 主要改动

### 1. Source slug 配置
- `workflows/rss_sources.yaml` 每个源新增 `slug` 字段（kebab-case）
- `workflows/collector.py` 读取 `slug`，缺失时抛 `ValueError`

### 2. 一次性迁移脚本
- `scripts/migrate_v04_to_v05.py`：
  - `--dry-run` / `--limit` 支持
  - 幂等检测：按 `key_insight` 存在性判定
  - `published_at` / `author` 从 `knowledge/raw/` 反查，未命中显式置 `null`
  - 调用 analyzer 补全 `key_insight`、`category`、`relevance_score`、`audience`
  - 多值 `category` 拆分：第一段保留，剩余进 `tags`，状态置 `review`
  - 文件重命名为 `<source-slug>-<YYYYMMDD>-<NNN>.json`

### 3. index.json 派生化
- 新建 `scripts/build_index.py`：全量扫描 `knowledge/articles/*.json` 重建索引
- `workflows/organizer.py` 删除所有 `index.json` 写入逻辑
- `workflows/graph.py` pipeline 末尾自动调用 `build_index()`

### 4. Analyzer prompt 与校验修正
- `category` prompt 改为枚举列表 + "select exactly one"，加反例
- `audience` 增加 3 个 few-shot 示例，要求先输出判断理由
- `relevance_score` 写全量，阈值淘汰改为写入 `_skipped.jsonl`
- `organizer.py` 增加 `category` 单值校验与降级逻辑

### 5. Collector 字段诚实化
- `author`：`entry.get("author") or None`，不再 fallback 到源 `name`
- `published_at`：`_parse_feed_pubdate(entry)`，解析失败写 `null`

### 6. 淘汰条目审计 `_skipped.jsonl`
- 新建 `workflows/skipped.py` 提供 `append_skipped()`
- analyzer 低分淘汰、reviewer 否决、organizer schema 校验失败均写入审计日志
- collector 分配编号时扫描 `articles/` 与 `_skipped.jsonl` 已用 id 并集

### 7. Validator 收紧
- `ID_PATTERN`：`^[a-z0-9-]+-\d{8}-\d{3}$`（禁止冒号）
- 新增必填字段：`key_insight`、`category`、`relevance_score`、`url`
- `category` 必须在枚举集合内
- `author` / `published_at` 允许为 `null`

## 端到端验证结果

- [x] 完整 pipeline 无报错（dry-run 与正常模式均通过）
- [x] `len(index.json) == 213 == len(glob articles/*.json)`
- [x] `category` 全部单值且在枚举集合内
- [x] 原 73 条 v0.4 条目均含 `key_insight`，文件名无冒号
- [x] 抽样旧条目：`author` / `published_at` 已清理为 `null`（源名与采集时间不再混入）
- [x] `_skipped.jsonl` 已产生 3 条审计记录

## 备注

- 迁移脚本消耗 API tokens 约 73 条 × 单次调用，费用 < $1
- 所有数据变更已落盘，`index.json` 已重建
- 如需回滚，可逐条 revert 文件重命名 + 字段恢复
