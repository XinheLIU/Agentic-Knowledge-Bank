# AI 知识库 · 技术规格
> Last updated: 2026-05-02

## 1. 采集层（Collector）
- **数据源**：
  - **GitHub Trending**：GitHub Search API v3 (`/search/repositories`)，OR 连接关键词 + 时间过滤 + stars 排序。认证使用 `GITHUB_TOKEN`。
  - **Hacker News**：Algolia HN Search API，关键词匹配 AI 相关故事。
  - **arXiv**：arXiv API，按分类（cs.AI 等）获取最新论文。
- **输出**：`knowledge/raw/{source}-{YYYY-MM-DD}.json`，顶层包含 `source`, `collected_at`, `query`, `count`, `items`。
- **每条 item 字段**：`id`(owner/repo), `title`, `description`, `url`, `stars`, `forks`, `language`, `topics`, `license`, `created_at`, `updated_at`, `open_issues`, `readme_excerpt`(可选)。
- **容错**：单条目失败应记录错误并跳过，不影响其他条目；API 限流时等待后重试，最多 3 次。

## 2. 分析层（Analyzer）
- **运行时**：OpenCode + LLM，Agent 通过 Skill 调用 LLM 分析。
- **输入**：`knowledge/raw/` 中的原始采集 JSON。
- **输出**：在原始 JSON 上 enrichment，每条 item 增加以下字段：
  ```json
  {
    "summary": "一句话中文摘要",
    "tags": ["tag1", "tag2"],
    "relevance_score": 0.8,
    "score_breakdown": {
      "tech_depth": 0.6,
      "practical_value": 0.7,
      "timeliness": 0.9,
      "community_heat": 0.85,
      "domain_match": 0.7
    },
    "analyzed_at": "2026-05-01T15:51:52Z"
  }
  ```
- **评分说明**：`relevance_score` 为 5 维度均值，低于 0.6 的条目由 Organizer 丢弃。
- **Prompt 原则**：摘要使用中文，标签使用英文小写连字符格式，不添加与内容无关的寒暄。

## 3. 整理层（Organizer）
- **输入**：`knowledge/raw/` 中已 enriched 的 JSON。
- **输出**：
  - 每条合格条目写入 `knowledge/articles/{YYYY-MM-DD}-{source}-{slug}.json`
  - 更新 `knowledge/articles/index.json`（含所有条目摘要和 `sources` 统计）
- **质量门控**：`relevance_score < 0.6` 的条目丢弃。
- **幂等性**：重复运行同一天不应产生重复条目。

## 4. 校验层（Hooks）
- **validate_json.py**：校验知识条目 JSON 必填字段、ID 格式、URL 格式、摘要长度、标签数量、status 合法性等。
- **check_quality.py**：5 维度质量评分（摘要质量/技术深度/格式规范/标签精度/空洞词检测），输出等级 A/B/C。
- **详见**：`spec/hooks-spec.md`

## 5. 触发层（Scheduler）
- **当前**：手动在 OpenCode 中调用 Agent 或使用 `@` 语法触发流水线。
- **调用方式**：
  ```
  @collector 采集今天的 GitHub Trending 数据
  @analyzer 分析 knowledge/raw/github-trending-2026-05-01.json
  @organizer 整理今天所有已分析的原始数据
  ```
- **未来**：迁移到 GitHub Actions 或定时触发。

## 6. 环境依赖
- **运行时**：OpenCode + LLM
- **数据源认证**：`GITHUB_TOKEN`（见 `.env.example`）
- **校验脚本**：Python 3.11+（hooks/ 目录），仅使用标准库
- **版本管理**：Git

## 7. 风险与兜底
- **GitHub API 限流**：读取 `X-RateLimit-Reset`，报告剩余等待时间；未认证 10 次/分钟，认证 30 次/分钟。
- **LLM 分析失败**：单条失败应记录错误并跳过，不影响其他条目。
- **数据格式异常**：写入 `knowledge/raw/errors-{date}.json` 供人工排查。
