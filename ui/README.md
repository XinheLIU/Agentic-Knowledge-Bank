# AI Knowledge Base UI

> Last updated: 2026-10-04

Notion-like 知识库管理面板：在 canonical SQLite 资产库之上浏览、检索与导出知识资产。

## 启动

```bash
uv run python ui/app.py          # 默认打开 knowledge/kb.sqlite
uv run python ui/app.py --db path/to/kb.sqlite --port 5050
```

`ui.app.main()` 是 UI 入口（`python ui/app.py` 启动）。

浏览器打开 http://localhost:5050

## 数据源

- **资产库**：`kb/store`（canonical SQLite asset store），只读展示 accepted 资产；
  superseded 条目默认隐藏（I4：accepted-only 读面）。
- **来源管理**：Horizon checkout 的 `data/config.json`。启用/禁用先验证后原子写入，
  验证失败时返回 400 且文件保持不变。
- **不再读取/写入** 旧版 `knowledge/articles/*.json` 与 `workflows/rss_sources.yaml`。

### 来源管理所需的运行时配置

来源管理是 provider 工具链的客户端，需要两项显式配置（都不再由本仓提供）：

| 变量 | 作用 | 默认 |
|---|---|---|
| `HORIZON_DIR` | 被管理的 Horizon checkout（读/写 `data/config.json`） | pin 文件；pin 文件已随 Horizon 打包迁至 agent-tools |
| `HORIZON_CONFIG_ROOT` | 校验 `data/config.json` 时使用的 Horizon profile 集（取该目录下的 `horizon-profiles/`） | 进程工作目录 |

两者都由 agent-tools 在**导入时**读取，因此必须在启动 UI 的进程环境中提前设置；
也可用 `python ui/app.py --horizon-dir <path>` 指定 checkout。
`HORIZON_CONFIG_ROOT` 未设置时，来源启停会因找不到 profile 集而返回 400——
这是配置缺失，不是配置缺陷。profile 的规范来源在 Information Assistant
（`information_assistant/resources/horizon-profiles/`），本仓只在测试中保留
仅含结构的夹具，见 [sibling-repo-failures.md](../docs/sibling-repo-failures.md) §4。

## 功能

- **浏览**：卡片列表（默认按评分排序），分页，排序（评分/更新/发布/标题）
- **筛选**：来源类型、profile、标签、状态、日期范围
- **搜索**：FTS5 关键词检索（CJK 支持，带 LIKE 降级；`/api/stats` 报告 `fts_mode`）
- **详情抽屉**：标题、摘要、评分理由、双语 enrichment blocks、标签、链接
- **多选导出**：勾选卡片 → 导出所选条目为 JSON
- **统计面板**：总数、来源类型数、标签数；侧栏版本号来自 `kb.store.model.project_version()`（G6：单一版本源）
- **五态**：初始（空库空列表）/ 加载 / 成功 / 空（"暂无数据"）/ 错误（红色提示条）均覆盖

## 资产写入语义（与旧版 UI 的差异）

资产在入库时**写一次即冻结**（asset-audit-model §5），因此 UI 不提供
编辑/删除/批量修改；重新采集同 ID/同 URL 条目由 admission ledger 记录为
`DUPLICATE_ID`/`DUPLICATE_URL`。旧「导入 JSON」由两条 canonical 路径替代：

```bash
information-run     # Horizon 采集 → admission ledger → 资产（Information Assistant）
python -m kb restore  # JSONL 快照重放（幂等）
```

`POST /api/articles/import-legacy` 仅用于 cutover 演练（ticket 14）：旧行经
`legacy:` ID 命名空间走同一 ingest 路径，损坏行计入可审计的 `failed`。

## API 端点

```
GET    /api/articles              # 列表（q/source_type/tag/profile/status/日期 + sort/pagination）
GET    /api/articles/<id>         # 详情（canonical 字段；未知 id → 404）
POST   /api/articles/export       # 按 ids 导出
POST   /api/articles/import-legacy# 仅限演练：旧行过 admission ledger（需 confirm:true）
GET    /api/stats                 # 统计 + version（单一版本源）+ fts_mode + 近期 runs
GET    /api/filters               # 筛选枚举值
GET    /api/sources               # Horizon 源快照（slug/name/类型/启用/近7天）
PATCH  /api/sources/<slug>        # 启用/禁用（先验证后写入；失败 400 且不落盘）
GET    /api/version               # 项目版本（G6）
GET    /healthz                   # 存活 + 库可读检查
```

## 技术栈

- 后端：Flask + `kb.store` AssetStore + `agent_tools.horizon.source_config`
- 前端：Vanilla JS + CSS（无框架依赖）
