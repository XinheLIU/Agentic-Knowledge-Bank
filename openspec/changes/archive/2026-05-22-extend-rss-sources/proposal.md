## Why

当前 `rss_sources.yaml` 只有 12 个源（7 启用），且 `collect_rss` 用单个全局 `limit` 跨源共享配额——靠前的源（如 HN）会吃光名额，后面的源拿不到任何条目。同时，转载场景下相同内容会以不同 URL 收两遍，浪费 LLM 调用。新加更多源前，这些底层问题必须先解决，否则加源等于没加。

## What Changes

- 在 `rss_sources.yaml` 中给每个源新增 `per_source_limit` 字段（默认 5）
- `collect_rss` 改为"每源独立配额 + 比例缩放"：当总配额需求超过全局上限时，按 `per_source_limit` 比例缩放
- Collector 末尾新增内容指纹去重：`normalize(title) + domain(url)`，跨源也能识别同一篇文章
- 新增 18 个 RSS 源（覆盖官方一手、AI 分析师、工程师/CS、新闻聚合）
- 启用原先禁用的 arXiv cs.CL
- UI 新增 L1 源管理：列出所有源、显示近 7 天采集数、支持启用/禁用

## Capabilities

### New Capabilities
- `rss-collection`: RSS 数据源配置、抓取与配额管理（包含 `per_source_limit`、比例缩放、内容指纹去重）
- `source-management-ui`: 知识库管理面板中的源列表查看与启用/禁用控制

### Modified Capabilities
<!-- 项目还没有正式 specs/，所有 capability 都是新建 -->

## Impact

- **代码**：
  - `workflows/rss_sources.yaml` 扩展 schema
  - `workflows/collector.py` 修改 `collect_rss()` 逻辑，新增 dedupe 函数
  - `ui/app.py` 新增 `GET /api/sources` 与 `PATCH /api/sources/<slug>` 两个端点
  - `ui/static/index.html` + `ui/static/js/app.js` 新增源管理视图
- **依赖**：不引入新依赖（继续用 `feedparser` / `httpx` / `pyyaml`）
- **数据**：不改动 `knowledge/articles/*.json` 已有格式；新去重逻辑只影响新采集条目
- **配置**：`AGENTS.md` 中"自动化规则"和"工作流规则"小节需要补充 per-source quota 和 dedupe 说明
