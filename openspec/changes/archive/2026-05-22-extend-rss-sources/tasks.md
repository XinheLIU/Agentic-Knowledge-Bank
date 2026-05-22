## 1. RSS yaml schema 扩展

- [x] 1.1 在 `workflows/rss_sources.yaml` 中为每个现有源添加 `per_source_limit` 字段（hn-best=10，其余 industry/open-source=5，research/framework=3）
- [x] 1.2 把 `arxiv-cs-cl` 改为 `enabled: true`
- [x] 1.3 追加 18 个新源条目（按 design.md 的 Decision 6 表格）

## 2. Collector 改造

- [x] 2.1 在 `workflows/collector.py` 顶部加常量 `DEFAULT_PER_SOURCE_LIMIT = 5`
- [x] 2.2 修改 `collect_rss(limit, config_path, articles_dir)`：解析 yaml 后计算每源实际配额（比例缩放，`max(1, ceil(...))`）
- [x] 2.3 把 `httpx.Client(timeout=20.0)` 改为 `httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))`
- [x] 2.4 实现 `_fingerprint(title, url) -> str`：lowercase + 去标点（保留 `\w` 与 `\u4e00-\u9fff`）+ `|` + netloc 去 `www.`
- [x] 2.5 实现 `_existing_fingerprints(articles_dir) -> set[str]`：扫 `articles/*.json` 重建
- [x] 2.6 在 `collect_rss` 末尾合并内存 dedupe + 历史 dedupe，命中则跳过
- [x] 2.7 写 `tests/test_collector.py::test_proportional_scaling`：构造 3 源 per_source_limit=[10,10,10]，global_cap=15，断言 actual=[5,5,5]（ceil 后）
- [x] 2.8 写 `tests/test_collector.py::test_per_source_limit_default`：源无 `per_source_limit` 时默认 5
- [x] 2.9 写 `tests/test_collector.py::test_min_quota_one`：缩放系数极小（0.1）时配额保底为 1
- [x] 2.10 写 `tests/test_collector.py::test_fingerprint_same_domain_normalized_title`：两条 title 仅大小写/标点不同、同 domain，dedupe 后只剩 1 条
- [x] 2.11 写 `tests/test_collector.py::test_fingerprint_different_domain_same_title`：同 title 不同 domain，dedupe 后保留 2 条
- [x] 2.12 写 `tests/test_collector.py::test_fingerprint_against_existing_articles`：articles_dir 已有匹配 fingerprint 的 json，新条目被丢弃

## 3. 手动连通性验证

- [x] 3.1 运行 `uv run python -m workflows.graph --sources rss --limit 30 --dry-run`，确认所有 enabled 源至少返回一次 HTTP 响应（log 中没有未处理异常）
- [x] 3.2 检查 dry-run 输出的源分布，确认 hn-best 没有吃光配额，simonwillison / antirez 等小源各至少 1 条

## 4. UI API: GET /api/sources

- [x] 4.1 在 `ui/app.py` 顶部加 `RSS_CONFIG = Path(__file__).resolve().parent.parent / "workflows" / "rss_sources.yaml"`
- [x] 4.2 实现 helper `_load_sources() -> list[dict]`：读 yaml，给每个源补默认 `enabled=True`、`per_source_limit=5`
- [x] 4.3 实现 helper `_last_7d_count_by_source(articles_dir) -> dict[str, int]`：扫 `articles/*.json`，按 `source` 字段聚合（注意 source 字段格式 `rss:<name>`，需匹配回 slug，或回退用 `id` 前缀）
- [x] 4.4 添加路由 `GET /api/sources`：组合两者返回 JSON 数组
- [x] 4.5 写 `tests/test_ui_sources.py::test_get_sources_lists_all`：模拟 yaml 含 2 源，断言返回 2 个对象，含必需字段
- [x] 4.6 写 `tests/test_ui_sources.py::test_get_sources_count_recent_only`：mock articles_dir 含 3 个近期 + 2 个 8 天前的 json，断言 `last_7d_count == 3`

## 5. UI API: PATCH /api/sources/<slug>

- [x] 5.1 实现 helper `_atomic_write_yaml(config, path)`：写 `path.with_suffix(".yaml.tmp")` 再 `os.replace`
- [x] 5.2 添加路由 `PATCH /api/sources/<slug>`：解析 body `{"enabled": bool}`，找到对应源、更新、原子写回
- [x] 5.3 未知 slug 返回 404，body 校验失败返回 400
- [x] 5.4 写 `tests/test_ui_sources.py::test_patch_toggles_enabled`：PATCH 后再次 GET 验证 enabled 变更
- [x] 5.5 写 `tests/test_ui_sources.py::test_patch_unknown_slug_404`：断言 404
- [x] 5.6 写 `tests/test_ui_sources.py::test_patch_preserves_other_sources`：toggle 一个源不影响其他源的字段

## 6. UI 前端：源管理视图

- [x] 6.1 在 `ui/static/index.html` 添加 "Sources" 导航入口
- [x] 6.2 在 `ui/static/js/app.js` 添加 `renderSourcesView()`：fetch `GET /api/sources`，渲染表格（slug / category / 7d count / toggle）
- [x] 6.3 toggle 变更时调用 `PATCH /api/sources/<slug>`，乐观更新 UI；失败则回滚并显示错误
- [x] 6.4 在 `ui/static/css/style.css` 添加 toggle 控件最小样式（用纯 checkbox 即可，不需额外库）
- [x] 6.5 手动验证：浏览器打开 → 看到所有源 → toggle 一个 → 刷新 → 状态保留

## 7. 文档与收尾

- [x] 7.1 更新 `AGENTS.md`：在"工作流规则"小节追加"per_source_limit + 比例缩放"和"fingerprint 去重"说明，并更新顶部 `Last updated`
- [x] 7.2 在 `AGENTS.md` 的"CLI 命令"小节补充访问 `/api/sources` 的简短说明
- [x] 7.3 运行 `uv run pytest -q -m non_llm` 全套通过
- [x] 7.4 运行一次真实 workflow：`uv run python -m workflows.graph --sources rss --limit 20`，确认 `knowledge/articles/` 新增条目分布合理（无单源垄断），UI 7d 计数同步更新
