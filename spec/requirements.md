# AI 知识库 · 需求规格
> Last updated: 2026-05-02

## 1. 用户与场景
- **服务对象**：我自己（单人本地使用）。
- **消费终端**：JSON 知识条目（`knowledge/articles/`），可通过 `index.json` 检索。
- **使用场景**：每天运行采集流水线，获取 AI/LLM/Agent 领域最新技术资讯；做技术选型时搜索 `knowledge/articles/` 中的条目。

## 2. 数据流

```
GitHub Search API / Hacker News API / arXiv API
    ↓
[Collector] 采集原始数据 → knowledge/raw/{source}-{date}.json
    ↓
[Analyzer]  LLM 分析 → knowledge/raw/ (enriched: 添加 summary/tags/relevance_score/score_breakdown)
    ↓
[Organizer] 筛选整理 → knowledge/articles/{date}-{source}-{slug}.json + index.json
```

三阶段 Agent 流水线，单向数据流，不可反向。

## 3. 数据源
- **GitHub Trending**：通过 GitHub Search API v3 (`/search/repositories`)，搜索最近 7 天 AI/LLM/Agent 相关热门仓库，按 stars 降序。
- **Hacker News**：通过 Algolia HN API，获取 AI 相关热门故事。
- **arXiv**：通过 arXiv API，获取 cs.AI 等分类最新论文。
- **时间**：只抓当天数据，不抓历史。冷启动前 3 天数据量可能不足，接受。

## 4. 采集过滤
- **GitHub**：搜索查询使用 OR 连接关键词（`AI`, `LLM`, `agent`, `RAG`, `MCP`, `agentic` 等），加 `created:>{7天前}` 时间过滤，Star >= 50，非 fork。
- **Hacker News**：关键词匹配标题/内容。
- **arXiv**：按分类过滤（cs.AI 等）。
- **维护**：`spec/keywords-v0.1.txt` 冷启动，根据漏抓情况手动补充。

## 5. Agent 分析输出

### 5.1 输入
- 原始采集数据（`knowledge/raw/` 中的 JSON）

### 5.2 输出格式
单个 JSON 文件，文件命名：`{YYYY-MM-DD}-{source}-{slug}.json`。

#### 字段结构
```json
{
  "id": "owner/repo",
  "title": "repo-name",
  "source": "github-trending",
  "source_url": "https://github.com/owner/repo",
  "url": "https://github.com/owner/repo",
  "collected_at": "2026-05-01T15:48:59Z",
  "analyzed_at": "2026-05-01T15:51:52Z",
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
  "status": "published",
  "stars": 928,
  "forks": 37,
  "language": "Python",
  "description": "original repo description",
  "topics": []
}
```

必须字段：`id`, `title`, `source`, `url`, `source_url`, `collected_at`, `summary`, `tags`, `relevance_score`

### 5.3 质量门控
- Analyzer 评分 `relevance_score` 低于 0.6 的条目，Organizer 应丢弃

## 6. 存储目录结构

```
ai-kb/
├── AGENTS.md                      # 项目记忆文件
├── project-vision.md              # 项目愿景
├── TODO.md                        # 待办事项
├── .env.example                   # 环境变量模板
├── .gitignore
├── hooks/                         # 校验与质量评分脚本
│   ├── validate_json.py
│   └── check_quality.py
├── spec/                          # 规格文档
│   ├── requirements.md
│   ├── tech-spec.md
│   ├── hooks-spec.md
│   ├── keywords-v0.1.txt
│   └── github-trending-skill-sepc.md
├── .opencode/                     # Agent 与 Skill 定义
│   ├── agents/
│   └── skills/
└── knowledge/
    ├── raw/                       # 原始采集数据（JSON）
    └── articles/                  # 整理后的知识条目（JSON）+ index.json
```

## 7. 验收标准（两周）

| 检查项 | 标准 | 状态 |
|---|---|---|
| 连续运行 | 7 天自动触发，无报错 | 待验收 |
| 产出总量 | knowledge/articles/ >= 60 条 | 待验收 |
| 有效知识 | relevance_score >= 0.6 的条目 >= 60 条 | 待验收 |
| 主动消费 | 至少 4 天查看采集结果 | 待验收 |
| 关键词迭代 | keywords.txt 至少更新过 1 次 | 待验收 |

**5/5 满足 = go，任一不满足 = no-go，项目关停。**
