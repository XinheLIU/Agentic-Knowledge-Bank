# 知识库内容混乱度审计与改进方案

> Last updated: 2026-05-13
> 范围：`knowledge/articles/` 下 140 个条目 + `knowledge/articles/index.json` + `knowledge/raw/` 4 份原始抓取
> 方法：脚本扫描全量字段分布、命名一致性、索引同步、时间戳/作者/分数语义

---

## 1. 一句话结论

**乱的根因不是数据脏，而是 schema 在演进过程中没有迁移历史数据**：旧条目按 v0.4 写入，新条目按 v0.5 写入，两代共存于同一目录，再叠加文件名规则不统一、index 不同步、若干字段是占位符而非事实，外观就乱了。

---

## 2. 关键证据（数字优先）

| 维度 | 现状 | 问题 |
|---|---|---|
| 总条目 | 140 | — |
| `status=review` / `published` | 73 / 67 | 一半条目卡在 review，无人晋级 |
| 含 `key_insight` / `category` / `relevance_score` / `url` | 67 / 140 | **新旧 schema 各占一半** |
| 文件名带冒号 `rss:reddit-...` | 64 / 140 | 与旧 `rss-NNN` 风格并存 |
| `index.json` 条目 | 67 | **与 FS 漂移：73 个条目未入索引** |
| `author == 源名`（"Reddit r/MachineLearning" 等） | 117 / 140 | 作者字段是占位符，不是真实作者 |
| `published_at == collected_at` | 117 / 140 | 发布时间被采集时间覆盖，等于丢失了真实发布时间 |
| `source = rss:Hacker News (Best)` 但实际是其他源 | 22（旧条目） | 旧 RSS 全部塌缩到一个源名 |
| 编号缺口 `(source, date)` 组 | 9 / 17 | 例：`rss-20260503-{2,3,4,5,6,9,11,13,14,15}` 全缺；说明分析/审核环节静默丢条目 |
| `category` 缺失 | 73 / 140 | 与旧 schema 一致 |
| `category` 用 `\|` 分隔多值（`agent\|evaluation`） | 4 | 非数组，下游难处理 |
| `category` 不在 `tags` 里 | 18 | 分类与标签不互推 |
| 数据源分布 | r/MachineLearning 95、HN 22、GitHub 23 | **68% 来自一个 subreddit**，覆盖窄 |
| `audience` 分布 | intermediate 125 / advanced 12 / beginner 3 | 几乎是常量，区分度为零 |
| `score` 分布 | min 5 / avg 7.46 / max 9 | 区间窄，集中在 7–8 |
| `relevance_score` 分布 | min 0.80 / avg 0.89 / max 0.95 | 区间被截断在 ≥0.80（应为入库阈值副作用） |

---

## 3. 七个根本问题（按影响排序）

### P0 — 双代 schema 共存，没有迁移
- 67 个新条目有 `key_insight / category / relevance_score / url / status=published`
- 73 个旧条目没有上述字段，`status=review`
- 同一目录两种 schema → 任何下游消费方都要写两条分支

**根因**：v0.4→v0.5 升级只改了写入路径，没回填历史数据（见 `openspec/changes/archive/2026-05-19-cleanup-knowledge-content/`）。
`workflows/organizer.py:70-84` 写的是新 schema，但旧文件原地不动。

### P1 — 文件名/ID 编码两套规则
```
旧：rss-20260502-001.json                        # 源信息丢失
新：rss:reddit-r-machinelearning-20260507-001.json  # 冒号在文件名里
```
- 旧规则把所有 RSS 塌缩成 `rss-`，丢失 feed 身份
- 新规则把 `source` 字段（含冒号、空格）直接当 slug，依赖 OS 对冒号的容忍（Windows/部分工具会出问题）
- `validate_json.py:32` 的 `ID_PATTERN` 允许冒号，等于事后追认而非设计

### P1 — `index.json` 与文件系统漂移
- 索引 67 条，文件 140 条 → **73 条孤儿**
- 新条目入库时同步索引（`organizer.py:120-127`），旧条目从未补登
- 任何依赖 index 的检索（如 MCP Server、UI）都会看到一半内容

### P1 — 作者与发布时间是占位符，不是事实
- `author = "Reddit r/MachineLearning"`：117 条用源名当作者
- `published_at == collected_at`：117 条把采集时间写进发布时间
- 这两个字段当前**无信息量**，但下游一旦信任会被误导（按"新发布"排序时全是采集顺序）
- 来源：`workflows/collector.py:115` `author = source.get("name", ...)`

### P2 — 编号缺口暗示静默丢条目
- 9/17 个 `(源, 日期)` 组有编号缺口
- 例：`rss-20260503` 缺 2,3,4,5,6,9,11,13,14,15（命名上规划了 16 条，只有 6 条入库）
- 说明 Analyzer/Reviewer 环节被淘汰的条目没有审计痕迹（pending_review/ 也没有，因为旧版本还没这个目录）

### P2 — 分类系统未收敛
- `category` 既有单值（`agent`）又有伪多值（`agent|evaluation` 字符串）
- 18 条 `category` 不在自身 `tags` 列表中
- `analyzer.py:58` prompt 给的合法集合：`llm|agent|rag|mcp|evaluation|deployment|security|other` —— 是**用 `|` 列举枚举值**的 prompt，被模型当成"用 `|` 分隔多值"复读了

### P3 — 维度区分度低
- `audience`：125/140 = intermediate（几乎常量）
- `score`：92% 落在 6–8
- `relevance_score`：被入库阈值截断在 0.80–0.95，无法用于排序
- 真实价值≈基于 `score` 的二分类（高/低），其他维度信息熵接近 0

---

## 4. 改进建议（按优先级与成本）

### 立刻做（低成本、收益大）

**S1. 回填迁移脚本，把旧 schema 升到新 schema**
推荐方案。一次性脚本，对 `status=review` 的 73 条：
1. 跑一次 analyzer 重新生成 `key_insight / category / relevance_score`
2. 改名重命名文件到新规则（含真实 feed slug）
3. 按 `source_url` 反查 `knowledge/raw/` 拿真实 `published_at` 和 `author`
4. 重建 `index.json`（全量重写而非增量追加）

**S2. `index.json` 改为派生产物**
不维护写入路径，每次运行末尾从 `knowledge/articles/*.json` 全量重建。
- 好处：永不漂移
- 代价：N 次磁盘读，对 140 条 < 50ms，不是瓶颈

**S3. 文件名规则收敛**
冒号从文件名里去掉，源 slug 标准化为 `[a-z0-9-]+`：
```
rss:reddit-r-machinelearning  →  reddit-ml
rss:hacker-news-best           →  hn-best
github                          →  github
```
在 `validate_json.py` 收紧正则，禁止冒号，强制 slug。

**S4. 修掉 analyzer prompt 的枚举歧义**
`workflows/analyzer.py:58` 把 `category: "llm|agent|rag|..."` 改成明确的"从下列**单一**值中选一个：[llm, agent, rag, ...]"，并在 organizer 校验为单值，多值改为 `tags` 表达。

### 这周做（中成本）

**S5. 区分 `published_at` 与 `collected_at`，找不到就显式标记 `null`**
不要让"采集时间"冒充"发布时间"。
```python
published_at = parse_feed_pubdate(entry) or None  # 真没有就 None，别 fallback
```

**S6. `author` 字段默认 `None`，不是源名**
源名已经在 `source` 字段里，重复一次没价值，反而误导。

**S7. 重置 `audience` 和 `relevance_score` 的语义或删除**
当前两个字段几乎是常量，不传递信息：
- `audience`：要么删，要么强制让 analyzer prompt 真的去判断（给 few-shot examples）
- `relevance_score`：保留但**不要在阈值过滤后再写入**，否则永远看不到 < 0.80 的样本（信息熵截断）。改为：写全量分数，UI 用阈值过滤展示。

**S8. 编号缺口审计**
被淘汰的条目要么进 `knowledge/pending_review/`，要么写 `knowledge/articles/_skipped.jsonl`（一行一条原因）。沉默丢失是 debug 的隐患。

### 下次大版本做（高成本）

**S9. 拓宽数据源**
68% 来自 r/MachineLearning，会形成视角偏差。建议加：
- arXiv（cs.CL / cs.LG 当日新增 trending）
- Anthropic / OpenAI / DeepMind blog（已在 RSS 配置但产出为 0？查 rss_sources.yaml）
- Twitter/X 列表的 webhook（如不接，可降级用 nitter RSS）

**S10. 标签层级化**
现在 16 个标签全是平的，导致 `agent / llm / evaluation` 三个标签覆盖了所有内容。建议两级：
```
domain: llm | agent | rag | mcp | infra
aspect: evaluation | deployment | security | reasoning | tool-use | fine-tuning
```
分类一般是 `domain × aspect` 的组合，而不是把它们塞进一个扁平 list。

---

## 5. 推荐执行顺序

```
1. 写迁移脚本 (scripts/migrate_v04_to_v05.py)            → 解决 P0
   └─ verify: 所有条目都有 key_insight / category / status=published
2. 重建 index.json，改为派生产物                          → 解决 P1
   └─ verify: index 条目数 == FS 条目数
3. 重命名 64 个含冒号文件 + 收紧 validator 正则           → 解决 P1
   └─ verify: validate_json.py 全量通过且禁止冒号
4. 修 analyzer prompt（单值 category）+ organizer 校验    → 解决 P2
   └─ verify: 新跑一批，category 全是单值
5. published_at / author 改为 nullable，不再 fallback     → 解决 P1
   └─ verify: 老条目从 raw/ 反查回填，新条目允许 null
6. 编号缺口写入 _skipped.jsonl                            → 解决 P2
   └─ verify: 同一 (source, date) 内 NNN 连续或在 _skipped 中可解释
```

每一步都有可验证的成功标准，可以独立提交。

---

## 6. 不建议做的事

- **不要在现有目录里区分新旧 schema 子目录**：会把"两代并存"问题永久化为目录结构。一次性迁移更干净。
- **不要写 schema 兼容层**：下游每个消费方都要再处理一次，比一次性回填贵。
- **不要因为 audience/relevance_score 区分度低就立刻删字段**：先确认它们的 prompt 是否真的让模型在判断，可能只是 prompt 描述太弱。
