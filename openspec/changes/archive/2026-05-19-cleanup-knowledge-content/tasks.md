## 1. 前置：source slug 配置

- [x] 1.1 给 `workflows/rss_sources.yaml` 每个源加 `slug` 字段（reddit-ml / hn-best / github / anthropic-blog 等），人工评审一遍
- [x] 1.2 在 `workflows/collector.py` 读取 slug，缺失时抛错而非 fallback 到 `name`

## 2. 一次性迁移脚本

- [x] 2.1 新建 `scripts/migrate_v04_to_v05.py` 骨架（参数：`--dry-run`、`--limit N`）
- [x] 2.2 实现"已迁移检测"：按 `key_insight` 字段存在与否判定，幂等跳过
- [x] 2.3 实现 `published_at`/`author` 从 `knowledge/raw/` 反查；命中 → 回填，未命中 → `null`
- [x] 2.4 调用现有 `workflows/analyzer.py` 对 73 条旧条目重跑生成 `key_insight / category / relevance_score / audience`（复用旧 `summary`/`tags`）
- [x] 2.5 拆分多值 `category`：取第一段，剩余进 `tags`
- [x] 2.6 文件重命名：旧 `<file>.json` → `<source-slug>-<YYYYMMDD>-<NNN>.json`，处理 (slug, date) 冲突时取下一个空号
- [x] 2.7 dry-run 跑一次，人工评审输出 diff
- [x] 2.8 正式跑迁移，commit 数据变更（73 条字段回填 + 文件改名）

## 3. index.json 派生化

- [x] 3.1 新建 `scripts/build_index.py`：扫描 `knowledge/articles/*.json`（排除 `_skipped.jsonl` 和 `index.json`），全量重建
- [x] 3.2 在 `workflows/organizer.py` 删除所有 `index.json` 写入逻辑（参考 review 文档 organizer.py:120-127）
- [x] 3.3 在 `workflows/graph.py` pipeline 末尾调用 `build_index.py`（或导入函数调用）
- [x] 3.4 单元测试：mock 文件系统跑 organizer，断言 `index.json` 路径无写入
- [x] 3.5 跑完整 pipeline 一次，校验 `len(index.json) == len(glob articles/*.json)`

## 4. Analyzer prompt 与校验修正

- [x] 4.1 修改 `workflows/analyzer.py` 的 prompt：`category` 从 `"llm|agent|rag|..."` 改为列表 + "select exactly one of"，加反例
- [x] 4.2 给 `audience` prompt 加 3 个 few-shot 示例（beginner/intermediate/advanced 各一），要求先输出判断理由
- [x] 4.3 改 analyzer 写入逻辑：`relevance_score` 写全量（不在写入前阈值过滤）
- [x] 4.4 在 `workflows/organizer.py` 加 `category` 单值校验，多值降级：取第一个值 + 其余进 `tags` + `status=review`
- [x] 4.5 单元测试：传入多值 `category` 字符串，断言降级行为正确

## 5. Collector 字段诚实化

- [x] 5.1 改 `workflows/collector.py:115` 的 `author = source.get("name", ...)` → `author = entry.get("author") or None`
- [x] 5.2 改 `published_at` 解析：`parse_feed_pubdate(entry) or None`，删除 `collected_at` fallback
- [x] 5.3 跑一次小批量采集（如 1 个源），人工检查输出 JSON 含 `null` 值正确

## 6. 淘汰条目审计 `_skipped.jsonl`

- [x] 6.1 新建工具函数 `workflows/skipped.py` 提供 `append_skipped(id, source, source_url, stage, reason)`，原子追加到 `knowledge/articles/_skipped.jsonl`
- [x] 6.2 在 `workflows/analyzer.py` 阈值淘汰处调用 `append_skipped(stage="analyzer")`
- [x] 6.3 在 `workflows/reviewer.py` 否决处调用 `append_skipped(stage="reviewer")`
- [x] 6.4 在 `workflows/organizer.py` schema 校验失败处调用 `append_skipped(stage="organizer")`
- [x] 6.5 改 `workflows/collector.py` 编号分配：扫描 articles/ 与 `_skipped.jsonl` 已用 id 的并集
- [x] 6.6 单元测试：模拟一次淘汰，断言一行被 append 到 `_skipped.jsonl`

## 7. Validator 收紧

- [x] 7.1 修改 `scripts/validate_json.py:32` 的 `ID_PATTERN`：禁止冒号，强制 `^[a-z0-9-]+-\d{8}-\d{3}$`
- [x] 7.2 加 v0.5 必填字段校验：`key_insight`、`category`、`relevance_score`、`url`
- [x] 7.3 `category` 必须是单值字符串且在枚举集合内
- [x] 7.4 允许 `author` / `published_at` 为 `null`
- [x] 7.5 跑 `validate_json.py` 对全量 213 条，确认通过

## 8. 端到端验证

- [x] 8.1 跑一次完整 pipeline，确认无报错
- [x] 8.2 校验 `index.json` 条目数 == articles JSON 文件数 == 213
- [x] 8.3 校验 `category` 字段全部单值且在枚举集合内
- [x] 8.4 校验 73 条原 v0.4 条目均含 `key_insight`、文件名无冒号
- [x] 8.5 抽样 10 条旧条目，确认 `author`/`published_at` 要么是真实值要么是 `null`，没有源名混入
- [x] 8.6 触发一次淘汰场景（如低分文章），确认 `_skipped.jsonl` 有记录
- [x] 8.7 新增 `docs/archive/knowledge-content-cleanup-report.md`，记录迁移前后数字对比
