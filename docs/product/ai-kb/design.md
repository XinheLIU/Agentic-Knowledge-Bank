# 技术设计：Horizon 雷达前端 + 资产库

> Status: **Accepted（已随 ticket 14–16 落地）** · Date: 2026-09-10 · Last updated: 2026-10-04 · 关联 PRD: [`docs/product/ai-kb/product.html`](product.html)（PRD 修订号见其更新记录）
> 覆盖需求：R-D1 … R-D7 · 解决阻塞项 B1（资产库形态）
> 参考实现：`/Users/xhl/GitHub/info-sources/reference/Horizon` @ `596e2b1`

---

## 1. 设计决策

### D-1 · 资产库形态 = SQLite 单文件

**决定**：新资产库使用 SQLite（Python 标准库 `sqlite3`），文件置于 `knowledge/kb.sqlite`。

**理由**
1. **图谱前置**：出界项"知识图谱/关联边"需要邻接查询，SQLite 的 `edges` 表让下一增量零迁移成本。
2. **全文检索**：Horizon 的 MCP 只暴露 run artifacts，没有跨历史检索；FTS5 恰好补上愿景里"检索命中率"这条成功指标。
3. **零新依赖**：`sqlite3` 是标准库，与项目"依赖极简"的既有取向（现有仅 5 个运行时依赖）一致。
4. **幂等天然**：`id` 作 PRIMARY KEY + `INSERT ... ON CONFLICT DO UPDATE` 直接满足 R-D3 的重跑幂等要求。
5. **消费面友好**：Flask UI 与 MCP server 都是 Python，`sqlite3` 直连，无序列化成本。

**被否决的替代**
| 方案 | 否决理由 |
|---|---|
| 沿用 JSON 文件 | 无索引、无事务、检索需全量扫描；图谱增量将被迫二次迁移 |
| 目录重排 | 只改组织方式，不解决查询能力，收益最低 |
| 外部向量库 | 引入重依赖；当前需求是关键词/过滤检索，不是语义检索 |

> 与工作区 AGENTS.md 对 `Agentic-Knowledge-Bank` 的"local SQLite RAG"描述一致。

### D-2 · 集成契约 = Horizon MCP（stdio JSON-RPC），非直接 import、非 CLI

**决定**：通过 `uv run horizon-mcp` 以 MCP 协议调用；核心工具 `hz_run_pipeline` → `hz_get_run_stage(run_id, "enriched")`。

**理由**
1. **这是 Horizon 公布的接口**：`src/mcp/README.md` 明确"exposes the native Horizon pipeline as staged tools"，并承诺"default to no extra side effects"。
2. **避开包名冲突**：Horizon 的 `pyproject.toml` 声明 `packages = ["src"]`，直接 import 会污染全局 `src` 命名空间。
3. **避开内部文件布局**：`data/mcp-runs/<run_id>/*.json` 是实现细节，MCP 工具名是契约，变更风险更低。
4. **免费获得 stage 重入**：可从 `raw` 缓存重跑 `enrich`，不需要重抓源。

**被否决的替代**
| 方案 | 否决理由 |
|---|---|
| `import src.orchestrator` | `src` 包名冲突，且绑定内部 API |
| subprocess `uv run horizon` | 只产出 markdown 简报，无结构化 enriched 产物 |
| 复制 Horizon 代码进本仓库 | fork 漂移，失去上游更新；违反"reference 只读"定位 |

### D-3 · 适配器拥有 schema，Horizon 可替换

**决定**：`ContentItem → 本库 schema` 的映射由本仓库的 `kb/horizon/mapper.py` 独占。Horizon 是**可替换的雷达实现**，不是数据模型的所有者。

**理由**：愿景的差异化在资产层（积累、检索、未来的关联），雷达是可替换前端。契约写在本侧，未来换雷达（或叠加第二个雷达）不动 schema。

---

## 2. 资产库 Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 条目主表
CREATE TABLE IF NOT EXISTS items (
  id                 TEXT PRIMARY KEY,   -- Horizon id: {source}:{subtype}:{native_id}
  source_type        TEXT NOT NULL,
  title              TEXT NOT NULL,
  url                TEXT NOT NULL,
  author             TEXT,
  published_at       TEXT,               -- ISO 8601, nullable
  fetched_at         TEXT NOT NULL,
  profile            TEXT,
  profile_method     TEXT,               -- source_override | ai_match
  profile_confidence REAL,
  profile_reason     TEXT,
  score              REAL,               -- 0–10
  score_reason       TEXT,
  summary            TEXT,
  content_main       TEXT,               -- split_content() 主体
  content_comments   TEXT,               -- split_content() 评论部分
  metadata_json      TEXT,               -- 原始 metadata 透传
  first_seen_at      TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_score     ON items(score DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_url ON items(url);   -- story 去重（R-D3 幂等）

-- 标签（规范化，供筛选）
CREATE TABLE IF NOT EXISTS tags (
  item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  tag     TEXT NOT NULL,
  PRIMARY KEY (item_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- 富化产物（双语）
CREATE TABLE IF NOT EXISTS artifacts (
  item_id  TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  language TEXT NOT NULL,                -- en | zh
  title    TEXT,
  PRIMARY KEY (item_id, language)
);

CREATE TABLE IF NOT EXISTS artifact_blocks (
  item_id   TEXT NOT NULL,
  language  TEXT NOT NULL,
  block_id  TEXT NOT NULL,
  title     TEXT,
  content   TEXT,
  is_primary INTEGER DEFAULT 0,
  position  INTEGER,
  PRIMARY KEY (item_id, language, block_id),
  FOREIGN KEY (item_id, language) REFERENCES artifacts(item_id, language) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifact_sources (
  item_id   TEXT NOT NULL,
  language  TEXT NOT NULL,
  source_id TEXT NOT NULL,
  title     TEXT,
  url       TEXT,
  PRIMARY KEY (item_id, language, source_id),
  FOREIGN KEY (item_id, language) REFERENCES artifacts(item_id, language) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS block_source_refs (
  item_id   TEXT NOT NULL,
  language  TEXT NOT NULL,
  block_id  TEXT NOT NULL,
  source_id TEXT NOT NULL,
  PRIMARY KEY (item_id, language, block_id, source_id)
);

-- 图谱占位（本增量不写入；下一增量直接复用，零迁移）
CREATE TABLE IF NOT EXISTS edges (
  src_id     TEXT NOT NULL,
  dst_id     TEXT NOT NULL,
  kind       TEXT NOT NULL,   -- same_story | same_topic | references | …
  weight     REAL,
  created_at TEXT,
  PRIMARY KEY (src_id, dst_id, kind)
);

-- 运行日志（对应埋点 pipeline.run.completed）
CREATE TABLE IF NOT EXISTS runs (
  run_id       TEXT PRIMARY KEY,
  started_at   TEXT NOT NULL,
  finished_at  TEXT,
  status       TEXT NOT NULL,            -- success | partial_failure | failure
  sources_json TEXT,
  fetched      INTEGER DEFAULT 0,
  scored       INTEGER DEFAULT 0,
  filtered     INTEGER DEFAULT 0,
  enriched     INTEGER DEFAULT 0,
  persisted    INTEGER DEFAULT 0,
  duration_ms  INTEGER
);

-- 全文检索
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
  title, summary, content_main, content_comments,
  content='items', content_rowid='rowid',
  tokenize='trigram'
);
```

**CJK 分词注意**：默认 `unicode61` 不切分中日韩文本，而本库内容是"英文源 + 中文摘要"混合。选用 `trigram`（SQLite ≥ 3.34）对 CJK 与子串匹配都可用。启动时探测 tokenizer 可用性，不可用则降级为 `unicode61` + `LIKE` 回退，并在启动日志显式告警（不留静默降级）。

**存储位置与版本管理**：`knowledge/kb.sqlite` 写入 `.gitignore`（二进制不做 git 追踪）；用 `kb export --format jsonl` 产出文本快照供周期提交，兼顾数据不丢与 diff 可读。

---

## 3. 适配器接口与模块边界

### 新增模块

```text
kb/
├── __init__.py
├── cli.py                 # 统一入口：kb horizon run | ingest | digest | serve | export
├── store/
│   ├── schema.py          # DDL + migrate()
│   ├── writer.py          # upsert_items(), record_run()
│   └── reader.py          # search(), get(), stats()
└── horizon/
    ├── client.py          # MCP stdio JSON-RPC 客户端
    └── mapper.py          # ContentItem -> store rows（D-3 的契约所有者）
```

### 关键签名

```python
# kb/horizon/client.py
class HorizonMCPClient:
    def __init__(self, horizon_dir: Path, timeout_s: float = 1800) -> None: ...
    def validate_config(self) -> dict: ...
    def run_pipeline(self, *, hours: int | None = None) -> str: ...        # -> run_id
    def get_run_stage(self, run_id: str, stage: str, max_items: int = 200) -> list[dict]: ...
    def get_run_summary(self, run_id: str, language: str = "zh") -> str: ...

# kb/horizon/mapper.py
def map_item(raw: dict) -> MappedItem:
    """ContentItem(dict) -> 规范化行集合；无 I/O，可单测。"""

# kb/store/writer.py
def upsert_items(conn: sqlite3.Connection, mapped: Iterable[MappedItem]) -> UpsertStats:
    """幂等写入：items 冲突按 id 更新，tags/artifacts 先删后插。"""

# kb/store/reader.py
def search(conn, *, q: str = "", source_type: str | None = None,
           min_score: float | None = None, language: str = "zh",
           limit: int = 20) -> list[dict]: ...
def get(conn, item_id: str) -> dict | None: ...
def stats(conn) -> dict: ...
```

### 端到端流程

```text
kb horizon run
  └─ HorizonMCPClient.run_pipeline()            → run_id
kb horizon ingest <run_id>
  ├─ get_run_stage(run_id, "enriched")          → [ContentItem]
  ├─ map_item() × N                             → [MappedItem]
  ├─ upsert_items()                             → 幂等落库
  └─ record_run()                               → runs 表
kb digest build [--since YYYY-MM-DD]
  ├─ reader.search(min_score=threshold)         → 当日高信号
  ├─ 渲染 EN + zh 两版 markdown                  → R-D4
  └─ 投递（SMTP / 可选飞书·webhook）              → R-D5
kb serve            → MCP over SQLite（R-D6，供下游 Agent）
ui/app.py           → 改为读 SQLite（R-D6，UI 保留）
```

---

## 4. 字段映射（Horizon → 本库）

| Horizon 来源 | 本库目标 | 说明 |
|---|---|---|
| `id` (`{source}:{subtype}:{native_id}`) | `items.id` | **原样保留含冒号**。旧 `validate_json.py` 的"禁止冒号"约束随旧 schema 一并废弃 |
| `source_type` | `items.source_type` | 枚举透传 |
| `title` / `url` / `author` | `items.title` / `url` / `author` | `url` 转 str |
| `published_at` / `fetched_at` | 同名列 | ISO 8601 |
| `metadata` | `items.metadata_json` | JSON 序列化透传 |
| `profile` | `items.profile` | |
| `processing.classification.method / confidence / reason` | `items.profile_method / profile_confidence / profile_reason` | |
| `processing.analysis.score` | `items.score` | 0–10 |
| `processing.analysis.reason` | `items.score_reason` | |
| `processing.analysis.summary` | `items.summary` | |
| `processing.analysis.tags[]` | `tags` 表 | 规范化为行 |
| `content`（按 `COMMENTS_MARKER` 切分） | `items.content_main` + `items.content_comments` | 复用 Horizon `split_content()` 语义 |
| `processing.artifacts[lang].title` | `artifacts.title` | lang ∈ {en, zh} |
| `processing.artifacts[lang].blocks[]` | `artifact_blocks` | `id/title/content/primary/position` |
| `processing.artifacts[lang].sources[]` | `artifact_sources` | `id/title/url` |
| `blocks[].source_refs[]` | `block_source_refs` | 引用关系 |

**不再存在的字段**（R-D7 结构性达成）：`personal_fit_score`、`learning_track`、`learning_tags`、`relevance_reason`、`priority_score`、`reading_priority`、`suggested_action`、`confidence`、旧 `relevance_score`/`score`(1-10 派生)——新 schema 中**没有任何对应列**，概念保留待 P1 用 Horizon profile 重实现。

---

## 5. 模块边界变更

| 现有模块 | 处置 | 说明 |
|---|---|---|
| `workflows/collector.py` | **退役** | 由 Horizon fetch 取代（R-D1） |
| `workflows/analyzer.py` | **退役** | 由 Horizon score+enrich 取代（R-D2） |
| `workflows/reviewer.py` / `reviser.py` | **退役** | Horizon 无对应；质量门控改为 profile threshold 单层过滤（顺带消除机会 O1"整批一刀切"） |
| `workflows/human_flag.py` | **退役** | Horizon 自带失败降级 |
| `workflows/organizer.py` | **退役** | 由 `kb/store/writer.py` 取代（R-D3） |
| `workflows/digest.py` | **已重写并移至 `kb/digest/`（ticket 13）** | 数据源从 JSON 目录改为 SQLite；新增双语（R-D4/R-D5）；legacy 模块随 ticket 16 删除 |
| `workflows/graph.py` / `state.py` / LangGraph | **已随 ticket 16 整体删除** | 雷达链路不再需要编排；未来"图谱/趋势"增量如需编排层，届时重新立项决定 |
| `hooks/validate_json.py` | **废止** | 随旧 schema 废弃（G1 的冒号矛盾随之消失） |
| `hooks/check_quality.py` | **已废止（ticket 16）** | 六维评分依赖旧字段；确定性逐条 admission（`kb/admission/`）取代其质量门控角色 |
| `mcp_knowledge_server.py` | **重写** | 改为读 SQLite（R-D6），同时修掉 G7 旧字段引用 |
| `ui/app.py` | **改造** | 读写 SQLite（R-D6）；UI 保留不弃用 |
| `prompts/`、`workflows/prompts.py` | **已删除（ticket 16）** | Horizon 负责 score+enrich，项目内不再有 LLM prompt 模板 |
| `workflows/relevance_profile.yaml` | **已删除（ticket 16）** | P1 个性化由项目自有的 Horizon profile（`horizon-profiles/ai-kb-personal/`）+ 确定性 admission 策略实现 |

---

## 6. 落地顺序

| 阶段 | 动作 | 验收 |
|---|---|---|
| S1 | 抽 20 份旧语料 → `tests/fixtures/legacy_articles/`；旧 `knowledge/articles/*.json` 归档 | R-D7 测试集就位 |
| S2 | `kb/store/` + schema + migrate + 单测 | `upsert_items` 幂等测试通过 |
| S3 | `kb/horizon/client.py`（MCP）+ `mapper.py` + 单测 | `map_item` 对样例 ContentItem 输出正确行 |
| S4 | `kb horizon run/ingest` 端到端 | 每日覆盖源 ≥5；条目落库 |
| S5 | `kb digest build` 双语 + 投递 | EN/zh 两份产出；SMTP 缺失优雅退出 |
| S6 | `kb serve` + `ui/app.py` 改 SQLite | 检索命中率 = 100%（fixtures 抽样） |
| S7 | 旧模块标记 deprecated | 无悬空引用 |

---

## 7. 风险与未决

| # | 风险 | 缓解 |
|---|---|---|
| K1 | Horizon 上游迭代快，MCP 工具契约可能变 | 锁定 clone 到具体 commit（当前 `596e2b1`）；`validate_config` 做启动自检；契约变更时只需改 `client.py` 一层 |
| K2 | FTS5 `trigram` 在旧 SQLite 不可用 | 启动探测 + 显式降级告警，不静默 |
| K3 | Horizon 需自己的 config/profiles，P0 缺"个性化" | P0 先用 `tech-news` profile + 自定义源清单跑通；个性化留 P1（B3） |
| K4 | `idx_items_url` 唯一约束可能误杀多源同 URL 的合法重复 | 落库前按 Horizon 的 story 去重结果为准，冲突时以 `ON CONFLICT` 更新为主而非丢弃 |
| K5 | SQLite 二进制不可 git diff，数据丢失风险 | `.gitignore` + `kb export --format jsonl` 周期快照提交 |
| K6 | 退役 LangGraph 后，未来图谱增量的编排层缺失 | 已随 ticket 16 删除；图谱增量立项时再决定重建或复用 |
| — | **已决**：`hooks/check_quality.py` 已随 ticket 16 废止 | 由 `kb/admission/` 的确定性 admission 接管质量门控 |

---

## 8. 未纳入本设计

图谱/关联边（`edges` 表已预留）、战略趋势提炼、认知模式预警、战略优先级仪表盘、可执行洞察库 —— 均属 PRD 出界项，重访条件 = 资产层上线 + 检索命中率证明复用价值。
