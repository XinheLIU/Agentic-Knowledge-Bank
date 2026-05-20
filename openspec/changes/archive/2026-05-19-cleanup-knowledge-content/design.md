## Context

`knowledge/articles/` 共 140 条，分两代 schema：v0.4（73 条，`status=review`，缺 `key_insight/category/relevance_score/url`）与 v0.5（67 条，`status=published`）。`index.json` 只索引了 67 条新条目，FS 漂移 73 条。文件名两套规则（`rss-NNN` vs `rss:reddit-...`）。117 条把源名当 `author`、把采集时间当 `published_at`。Analyzer prompt 用 `|` 列举枚举值，导致 4 条 `category` 被模型当成多值字符串。淘汰条目无审计痕迹，编号缺口 9/17。

约束：
- 不改动现有 LangGraph 工作流结构（`graph.py` 编排不动）
- 不引入新依赖（`uv` 当前栈：langchain / langgraph / pyyaml / pydantic）
- 迁移必须可重入：脚本重跑结果一致
- 历史 `raw/` 只有 4 份原始抓取 → analyzer 重跑对没有 `raw` 的旧条目要降级处理（不靠 raw 反查时承认字段为 `null`）

## Goals / Non-Goals

**Goals:**
- 一次性把 140 条收敛到 v0.5 单一 schema
- 消灭 `index.json` 漂移，使其成为派生产物
- 文件名/ID 规则唯一、validator 强制
- `author` / `published_at` 字段语义诚实（不知道就 `null`）
- 淘汰条目可审计

**Non-Goals:**
- S9（拓宽数据源）和 S10（标签层级化）不在本次范围
- 不重构 LangGraph 节点结构
- 不改动 MCP Server / UI 消费侧代码（只保证它们拿到的 index 是全量且诚实的）
- 不删除 `audience` / `relevance_score` 字段（先修语义再观察）

## Decisions

### D1. 迁移走一次性脚本，不走运行时兼容层
- **选择**：`scripts/migrate_v04_to_v05.py` 单次跑，原地改写 73 条旧文件
- **替代**：在 organizer 加 schema 适配层，读时升级
- **理由**：兼容层把"两代并存"固化进代码，每个下游消费方都要再处理一次。一次性迁移 73 条成本 < 50 美分（analyzer 重跑），换永久干净 schema。

### D2. `index.json` 不再增量写入，全量重建
- **选择**：新增 `scripts/build_index.py`，pipeline 末尾调用；删除 `organizer.py` 的 `index.json` 写入分支
- **替代**：保留增量写入，加一致性校验
- **理由**：140 条全量扫描 < 50ms，不是瓶颈。增量路径只要存在就会漂移，校验也不如不写。

### D3. 文件名 slug 规则
- `source` 字段保留人类可读（如 `"rss:Reddit r/MachineLearning"`），但文件名/ID 用 slug：`reddit-ml`、`hn-best`、`github`
- 文件名格式：`<source-slug>-<YYYYMMDD>-<NNN>.json`，正则 `^[a-z0-9-]+-\d{8}-\d{3}$`
- slug 映射写在 `workflows/rss_sources.yaml` 里每个源加一个 `slug:` 字段，缺省时从 `name` 派生

### D4. `category` 单值，多值走 `tags`
- analyzer prompt 改为枚举列表+"选一个"指令，给一个反例（"不要返回 `agent|evaluation`"）
- organizer 校验 `category in {llm, agent, rag, mcp, evaluation, deployment, security, other}`，违例标记 review
- 已有 4 条多值的，迁移脚本里拆分：`category = 第一个值`，其余进 `tags`

### D5. `author` / `published_at` 缺失即 `null`，不 fallback
- collector：`published_at = parse_feed_pubdate(entry) or None`，`author = entry.author or None`（不再 `or source.name`）
- JSON schema 允许这两个字段为 `null`；validator 不强制非空
- 迁移脚本对 73 条旧条目：能从 `raw/` 反查就回填，反查不到就显式置 `null`

### D6. 淘汰条目走 `_skipped.jsonl`
- 路径：`knowledge/articles/_skipped.jsonl`（一个文件，append-only，行 JSON）
- 字段：`{id, source, source_url, stage, reason, ts}`
- 写入点：analyzer 判定 `relevance_score < 阈值`、reviewer 判定不通过、organizer 校验失败
- `id` 与 articles 共享同一编号空间，所以编号缺口可以回查到原因

### D7. `relevance_score` 写全量，阈值过滤移到展示层
- analyzer 永远写真实分数到 JSON（即便 < 0.80）
- 阈值过滤只决定 `status` 走 `published` 还是淘汰到 `_skipped.jsonl`
- 留在 articles/ 里的条目分数仍可能 < 0.80（如果策略放宽），UI 自己过滤

### D8. `audience` 用 few-shot 修 prompt
- 当前 prompt 描述弱 → 模型 125/140 输出 intermediate
- 给 3 个 few-shot 示例（beginner / intermediate / advanced 各一），并要求模型先输出"判断理由"再给值
- 这一项是 prompt 改动，不改 schema

## Risks / Trade-offs

- **Risk**: 迁移脚本重跑 analyzer 会花 API 费用（73 条 × Opus/Sonnet 单次） → **Mitigation**: 用项目当前 model_client 的默认模型（Sonnet 4.6），73 条估算 < $1；脚本设计可重入，失败可断点续跑（按文件存在的 v0.5 字段判断是否已迁移）。
- **Risk**: 73 条旧条目大多没有对应 `raw/` 抓取（只有 4 份），`published_at` / `author` 大量为 `null` → **Mitigation**: 这就是诚实的代价，承认信息缺失比假装有强。UI 显示"未知发布时间"即可。
- **Risk**: 文件重命名会让外部链接/缓存失效 → **Mitigation**: 项目内部还没有外部引用 index 的消费者（MCP/UI 还在迭代），现在是最低成本窗口。
- **Risk**: `_skipped.jsonl` 与 articles 共享 id 空间，但 collector 在分配 NNN 时只看 articles 目录会撞号 → **Mitigation**: collector 分配编号时同时扫描 `_skipped.jsonl` 已用 id。
- **Risk**: validator 收紧后旧 CI 跑历史快照会红 → **Mitigation**: 迁移在 validator 收紧之前提交；同一 PR 内顺序：迁移 → 收紧 validator。

## Migration Plan

1. 写 `scripts/migrate_v04_to_v05.py`，dry-run 模式先打印将改动的 73 个文件
2. 跑迁移，commit 改名 + 字段回填的产物（不含代码改动）
3. 写 `scripts/build_index.py`，全量重建 `index.json`，commit
4. 改 `workflows/organizer.py` 删除 index 增量写入，pipeline 末尾改调 `build_index.py`
5. 改 `workflows/collector.py`：`author`/`published_at` 不 fallback；`workflows/analyzer.py`：prompt 改 category 单值 + audience few-shot
6. 改 `scripts/validate_json.py`：ID 正则禁止冒号
7. 加 `_skipped.jsonl` 写入逻辑到 analyzer/reviewer/organizer

回滚：每步独立 commit，可逐步 revert。迁移脚本本身设计为可重入，重跑安全。

## Open Questions

- analyzer 重跑时是否复用旧条目的 `summary`/`tags`？倾向于**复用**（已经经过 review），只补缺失字段。
- `relevance_score` 写全量后，当前 `status=review` / `published` 的语义是否还需要？倾向于**保留**，`published` = 通过阈值且 reviewer 放行，`review` = 待人工，淘汰 = `_skipped.jsonl`。
