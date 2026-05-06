# AI 知识库 · 技术规格
> Last updated: 2026-05-06

## 1. 工作流拓扑

当前版本使用 LangGraph，节点顺序如下：

```text
plan -> collect -> analyze -> review
                             | pass -> organize -> END
                             | fail & iteration < max -> revise -> review
                             | fail & iteration >= max -> human_flag -> END
```

共享状态定义在 `workflows/state.py`，核心字段包括：
- `plan`
- `requested_sources`
- `sources`
- `analyses`
- `articles`
- `review_feedback`
- `review_passed`
- `iteration`
- `needs_human_review`
- `cost_tracker`

## 2. Planner
- 根据目标条数选择 `lite` / `standard` / `full`
- 输出 `per_source_limit`、`relevance_threshold`、`max_iterations`
- 只规划，不执行采集或分析

## 3. Collector
- **数据源**：
  - GitHub Search API v3 (`/search/repositories`)
  - RSS（配置文件 `workflows/rss_sources.yaml`）
- **输入**：`requested_sources` + `plan.per_source_limit`
- **输出**：原始条目列表，字段包括 `id`, `title`, `source`, `source_url`, `url`, `raw_description`, `collected_at`
- **容错**：单一数据源失败不应阻塞其他源

## 4. Analyzer
- 对每条原始条目单独调用 LLM
- 输出：
  ```json
  {
    "summary": "中文技术摘要",
    "tags": ["llm", "agent"],
    "relevance_score": 0.8,
    "category": "agent",
    "key_insight": "一句话洞察",
    "score": 7,
    "audience": "intermediate",
    "status": "review"
  }
  ```
- LLM 失败时降级为低分草稿，保留溯源字段

## 5. Reviewer / Reviser
- Reviewer 让 LLM 给出五维分数：
  - `summary_quality`
  - `technical_depth`
  - `relevance`
  - `originality`
  - `formatting`
- 加权总分由代码重算，阈值 `>= 7.0` 视为通过
- 未通过且未达到 `max_iterations` 时进入 Reviser
- Reviser 读取 `review_feedback`，只修改 `analyses`

## 6. Organizer / HumanFlag
- Organizer 按 `relevance_threshold` 过滤、按 `source_url` 去重、生成 hook 兼容文章 JSON、更新 `knowledge/articles/index.json`
- HumanFlag 在审核循环用尽时将现场写入 `knowledge/pending_review/`
- Organizer 输出应满足 `hooks/validate_json.py` 的必填与 ID 规则

## 7. 校验层（Hooks）
- `validate_json.py`：校验必填字段、ID 格式、URL、摘要长度、标签、status、score、audience
- `check_quality.py`：五维质量评分，等级 A/B/C
- 文章发布目标：至少达到 B

## 8. 运行与调度
- CLI：`uv run python -m workflows.graph --sources github,rss --limit 20`
- CI：GitHub Actions 每日触发 `uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag`
- CI 只提交 `knowledge/articles/` 与 `knowledge/raw/`，不提交 `knowledge/pending_review/`
- notebook：`notebooks/langgraph_workflow_demo.ipynb` 用于演示状态与节点职责

## 9. 测试分层
- `non_llm`：默认 deterministic pytest 路径，所有 LLM 调用均 mock 或绕开
- `llm_e2e`：真实 provider 的端到端验证，运行真实 `run_workflow()`，并在临时目录验证产出
- 独立文档：`spec/testing-strategy.md`
