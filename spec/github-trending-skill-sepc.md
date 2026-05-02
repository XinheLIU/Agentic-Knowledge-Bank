# skill: github-trending · 需求

> Last updated: 2026-05-01

## 要做什么
- 通过 GitHub Search API 搜索最近 7 天内 AI/LLM/Agent 相关的热门仓库
- 过滤高质量仓库（Star >= 50、有英文 description、非 fork）
- 排除 awesome-list、课程作业、个人笔记等低价值类型
- 输出结构化 JSON 文件，字段包括基础元数据与可选 README 摘录

## 不做什么
- 不走 HTML 解析（GitHub Trending 页面结构不稳定，API 更可靠）
- 不做去重（由 caller 处理）
- 不自动建立知识关联或图谱

## 采集步骤

### 1. 构造搜索请求

```
GET https://api.github.com/search/repositories
```

**查询参数**：
- `q`: 组合以下关键词（OR 连接）：`AI`, `LLM`, `"large language model"`, `agent`, `RAG`, `MCP`, `"model context protocol"`, `"agentic"`
- 加上时间过滤：`created:>{7天前的日期}` 或 `pushed:>{7天前的日期}`
- `sort`: `stars`
- `order`: `desc`
- `per_page`: `30`

**请求头**：
```
Accept: application/vnd.github.v3+json
Authorization: Bearer ${GITHUB_TOKEN}
```

### 2. 过滤结果

- Star 数 >= 50
- 有英文 description
- 非 fork 仓库（`fork: false`）
- 排除 awesome-list、课程作业、个人笔记

### 3. 提取元数据

```json
{
  "id": "{owner}/{repo}",
  "title": "{repo name}",
  "description": "{repo description}",
  "url": "{html_url}",
  "stars": "{stargazers_count}",
  "forks": "{forks_count}",
  "language": "{language}",
  "topics": ["{topics array}"],
  "license": "{license.spdx_id}",
  "created_at": "{created_at}",
  "updated_at": "{pushed_at}",
  "open_issues": "{open_issues_count}"
}
```

### 4. 增强信息（可选）

对 Star 数 Top 5 的仓库，额外获取 README 前 500 字存入 `readme_excerpt` 字段。

### 5. 输出

- 文件路径：`knowledge/raw/github-trending-{YYYY-MM-DD}.json`
- 顶层包含 `source`, `collected_at`, `query`, `count`, `items`
- 使用 2 空格缩进

## 边界 & 验收

- 单次执行 < 10s
- 采集条目数 15-30 条为正常范围；少于 10 条报告关键词需扩展，多于 50 条提高 Star 阈值
- 输出必须通过 jsonschema 验证
- 错误处理策略：
  - HTTP 401：检查 GITHUB_TOKEN 是否设置
  - HTTP 403 (rate limit)：读取 `X-RateLimit-Reset`，报告剩余等待时间
  - HTTP 422 (bad query)：简化查询条件后重试
  - 网络超时：等待 5 秒后重试，最多 3 次

## 怎么验证

- 跑 `skill-invoke github-trending` 后，检查输出文件存在且 JSON 字段完整
