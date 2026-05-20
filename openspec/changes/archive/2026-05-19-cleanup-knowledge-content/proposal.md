## Why

知识库 140 个条目存在双代 schema 共存、index 与文件系统漂移、文件名规则不统一、占位符字段污染真实语义、分类多值化、淘汰条目静默丢失等问题（见 `docs/archive/knowledge-content-review.md`）。下游消费方（MCP Server、UI、排序/检索）已经被迫处理两套数据形态，再不收敛会把"两代并存"固化进目录结构。

## What Changes

- **BREAKING** 文件名/ID 规则收敛：`source` slug 标准化为 `[a-z0-9-]+`，禁止冒号；旧 `rss-NNN` 与新 `rss:...` 统一为 `<source-slug>-<YYYYMMDD>-<NNN>`
- **BREAKING** `index.json` 改为派生产物：取消增量写入路径，每次 pipeline 运行末尾从 `knowledge/articles/*.json` 全量重建
- **BREAKING** `author` 与 `published_at` 在缺失真实值时写 `null`，不再用源名/采集时间 fallback
- Analyzer prompt 把 `category` 从枚举字符串 `"llm|agent|rag|..."` 改成"从下列单一值中选一个"，organizer 校验单值，多值改走 `tags`
- `audience` / `relevance_score` 语义修正：`audience` 给 few-shot 让模型真的判断；`relevance_score` 写全量分数，阈值过滤移到展示层
- Analyzer/Reviewer 淘汰的条目写入 `knowledge/articles/_skipped.jsonl`（一行一条，含 id、源、原因），消除编号缺口里的静默丢失
- 一次性迁移脚本 `scripts/migrate_v04_to_v05.py` 把 73 条 v0.4 旧条目回填到 v0.5：重跑 analyzer 生成 `key_insight/category/relevance_score`、按 `source_url` 反查 `raw/` 还原 `published_at/author`、改名到新文件规则、重建 index

## Capabilities

### New Capabilities

- `knowledge-schema`: 文章 JSON 的字段语义（含 nullable 规则）、ID 与文件名格式、source slug 规范
- `knowledge-index`: `index.json` 作为派生产物的构建与一致性约束
- `knowledge-analyzer-output`: analyzer 产出的 category 单值约束、audience/relevance_score 写入语义
- `knowledge-collector-defaults`: collector 对 `author` / `published_at` 缺失值的处理
- `knowledge-pipeline-audit`: 淘汰条目的 `_skipped.jsonl` 审计日志
- `knowledge-migration-v04-v05`: 一次性把 v0.4 历史条目迁移到 v0.5 的脚本

### Modified Capabilities

<!-- 当前 openspec/specs/ 为空，所有能力为新增 -->

## Impact

- 代码：`workflows/collector.py`（author/published_at fallback）、`workflows/analyzer.py`（prompt + category 单值）、`workflows/organizer.py`（index 写入路径下线、单值校验、skipped 日志）、`workflows/reviewer.py`（skipped 日志）、`scripts/validate_json.py`（ID 正则收紧）
- 新文件：`scripts/migrate_v04_to_v05.py`、`scripts/build_index.py`、`knowledge/articles/_skipped.jsonl`
- 数据：73 条 v0.4 旧条目重命名 + 字段回填；64 个含冒号文件名重命名；`index.json` 全量重写
- 下游：依赖 `index.json` 的检索/UI 一次性看到全部 140 条；依赖 `author`/`published_at` 字段的代码要处理 `null`
