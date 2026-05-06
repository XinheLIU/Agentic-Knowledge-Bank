# AI 知识库 · 需求规格
> Last updated: 2026-05-06

## 1. 用户与场景
- **服务对象**：我自己（单人本地使用）
- **消费终端**：`knowledge/articles/` 下的 JSON 条目与 `index.json`
- **使用场景**：每天运行工作流获取 AI/LLM/Agent 最新技术内容；做技术选型与学习整理时检索本地知识库

## 2. 工作流目标
- 使用 LangGraph 显式表达节点、状态与条件路由
- 保留 GitHub 与 RSS 采集能力
- 在分析后增加审核/修订闭环，而不是一次分析后直接入库
- 审核失败达到上限时，必须走人工介入分支，不进入正式知识库

## 3. 数据流

```text
GitHub Search API / RSS
    ↓
[Planner] 规划执行策略
    ↓
[Collector] 采集原始数据
    ↓
[Analyzer] 单条 LLM 分析
    ↓
[Reviewer] 五维加权审核
    ↓ pass
[Organizer] 发布到 knowledge/articles/ + index.json

或

[Reviewer] 未通过
    ↓
[Reviser] 定向修改
    ↓
[Reviewer] 再审核
    ↓ 超过上限
[HumanFlag] 写入 knowledge/pending_review/
```

## 4. 数据源
- **GitHub**：最近 7 天 AI/LLM/Agent 相关热门仓库，按 stars 降序
- **RSS**：由 `workflows/rss_sources.yaml` 配置，支持开关单个源
- **时间范围**：以当次运行实时采集为主，不要求历史补采

## 5. 文章输出要求

输出文件写入 `knowledge/articles/*.json`，至少包含：

```json
{
  "id": "github-20260506-001",
  "title": "repo-name",
  "source_url": "https://github.com/owner/repo",
  "summary": "中文技术摘要",
  "tags": ["llm", "agent"],
  "status": "published"
}
```

常见附加字段：
- `source`
- `url`
- `collected_at`
- `score`
- `audience`
- `relevance_score`
- `category`
- `key_insight`

## 6. 质量门控
- `relevance_score` 低于 Organizer 阈值的条目不入库
- Reviewer 总分由代码按权重计算，不信任 LLM 算术
- 进入 `knowledge/articles/` 的条目应通过 `validate_json.py`，并在 `check_quality.py` 中达到 B 或以上

## 7. 验收标准

| 检查项 | 标准 | 状态 |
|---|---|---|
| 运行入口 | `uv run python -m workflows.graph` 可执行 | 待验收 |
| 条件路由 | pass / revise / human_flag 三种路径可测 | 待验收 |
| 文章契约 | 输出满足 hooks 校验 | 待验收 |
| 自动化 | GitHub Actions 使用新入口，且 `human_flag` 返回非零退出码 | 待验收 |
| 测试分层 | `non_llm` 与 `llm_e2e` 两条测试路径独立可运行 | 待验收 |
| 文档一致性 | README / AGENTS / spec 与代码一致 | 待验收 |
