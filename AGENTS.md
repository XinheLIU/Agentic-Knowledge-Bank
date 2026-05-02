# AGENTS.md — AI 知识库项目

> Last updated: 2026-05-02
> 本文件是项目的"大脑"——OpenCode 启动时自动加载，指导所有 Agent 的行为。

## 项目定义

**AI Knowledge Base（AI 知识库）** 是一个自动化技术情报收集与分析系统。
它持续追踪 GitHub Trending、Hacker News、arXiv 等来源，将分散的技术资讯
转化为结构化、可检索的 JSON 知识条目。

### 核心价值
- 每日自动采集 AI/LLM/Agent 领域的高质量技术文章与开源项目
- 通过 Agent 协作完成 **采集 → 分析 → 整理 → 保存** 四步流水线
- 输出格式统一的 JSON 知识条目，便于下游应用消费
- 写入知识条目时自动触发 JSON 格式校验与质量评分钩子

## 项目结构

```
ai-kb/
├── AGENTS.md                          # 项目记忆文件（本文件）
├── project-vision.md                  # 项目愿景与 go/no-go 验收标准
├── TODO.md                            # 待办事项
├── pyproject.toml                     # Python 依赖与工具配置
├── .env.example                       # 环境变量模板
├── .gitignore
├── .opencode/
│   ├── agents/
│   │   ├── collector.md               # 采集 Agent 角色定义
│   │   ├── analyzer.md                # 分析 Agent 角色定义
│   │   └── organizer.md               # 整理 Agent 角色定义
│   ├── skills/
│   │   ├── github-trending/SKILL.md   # GitHub Trending 采集技能
│   │   ├── hackernews/SKILL.md        # Hacker News 采集技能
│   │   ├── arxiv/SKILL.md             # arXiv 论文采集技能
│   │   ├── tech-summary/SKILL.md      # 技术摘要生成技能
│   │   ├── markdown-writer/SKILL.md   # Markdown 写入技能
│   │   ├── metrics-tracker/SKILL.md   # Pipeline 指标记录技能
│   │   ├── grill-me/SKILL.md          # 设计压力测试技能
│   │   ├── write-a-skill/SKILL.md     # 技能创建技能
│   │   └── to-issues/SKILL.md         # 计划拆解为 issue 技能
│   └── plugins/
│       └── validate.ts                # OpenCode 写入钩子：自动校验 + 质量评分
├── pipeline/                          # 核心流水线代码
│   ├── __init__.py
│   ├── pipeline.py                    # 四步流水线主控
│   ├── rss_reader.py                  # RSS 采集（feedparser）
│   ├── model_client.py                # 多模型 LLM 客户端
│   └── rss_sources.yaml               # RSS 源配置
├── scripts/                           # 兼容旧路径的别名入口
│   ├── __init__.py
│   ├── pipeline.py                    # → pipeline/pipeline.py
│   ├── rss_reader.py                  # → pipeline/rss_reader.py
│   └── model_client.py                # → pipeline/model_client.py
├── mcp_knowledge_server.py            # MCP Server：知识库搜索（JSON-RPC 2.0 over stdio）
├── opencode.json                      # OpenCode MCP 配置
├── .claude/mcp.json                   # Claude Code MCP 配置
├── .codex/mcp.json                    # Codex MCP 配置
├── hooks/                             # 质量门控脚本
│   ├── validate_json.py               # JSON Schema 校验
│   └── check_quality.py               # 五维度质量评分
├── tests/                             # pytest 测试套件
├── spec/
│   ├── requirements.md                # 需求规格
│   ├── tech-spec.md                   # 技术规格
│   ├── keywords-v0.1.txt              # 关键词过滤词表
│   └── github-trending-skill-sepc.md  # GitHub Trending 技能规格
└── knowledge/
    ├── raw/                           # 原始采集数据（JSON）
    └── articles/                      # 整理后的知识条目（JSON）
```

## 编码规范

### 文件命名
- 原始数据：`knowledge/raw/{source}-{YYYY-MM-DD}.json`
  - 例：`knowledge/raw/github-trending-2026-05-01.json`
  - 例：`knowledge/raw/hackernews-top-2026-05-01.json`
  - 例：`knowledge/raw/arxiv-csai-2026-05-01.json`
- 知识条目：`knowledge/articles/{YYYY-MM-DD}-{source}-{slug}.json`
  - 例：`knowledge/articles/2026-05-01-github-trending-library-skills.json`
- 索引文件：`knowledge/articles/index.json`
- **版本库**：上述目录中的 `*.json` 由 `.gitignore` 排除，仅为本地流水线产出；仓库内保留空目录占位（`.gitkeep`）。要对格式与质量脚本做手动校验，可使用 `tests/fixtures/articles/example-published.json`。

### JSON 格式(知识条目格式)
- 使用 2 空格缩进
- 日期格式：ISO 8601（`YYYY-MM-DDTHH:mm:ssZ`）
- 字符编码：UTF-8
- 知识条目必须包含的字段：`id`, `title`, `source`, `source_url`, `collected_at`, `summary`, `tags`, `score`
- 知识条目常见附加字段：`analyzed_at`, `score_breakdown`, `status`, `stars`, `forks`, `language`, `description`, `topics`, `audience`

### 语言约定
- 代码、JSON 键名、文件名：英文
- 摘要、分析、注释：中文
- 标签（tags）：英文小写，用连字符分隔（如 `large-language-model`）

## 工作流规则

### 四步流水线

```
[Collector]  ──采集──→ knowledge/raw/
                           │
[Analyzer]   ──分析──→ knowledge/raw/ (enriched)
                           │
[Organizer]  ──整理──→ knowledge/articles/
                           │
[Save]       ──保存──→ knowledge/articles/*.json
                           │
[Hook]       ──校验──→ JSON 格式 + 质量评分（>= B 级）
```

### Agent 协作规则

1. **单向数据流**：Collector → Analyzer → Organizer → Save，不可反向
2. **职责隔离**：每个 Agent 只操作自己权限范围内的文件
3. **幂等性**：重复运行同一天的采集不应产生重复条目
4. **质量门控**：Analyzer 评分低于 0.6 的条目，Organizer 应丢弃；Hook 评分低于 B 级会发出警告
5. **可追溯**：每个条目保留 `source_url` 和 `collected_at` 用于溯源
6. **自动校验**：通过 OpenCode 插件，每次写入 `knowledge/articles/*.json` 时自动运行 `validate_json.py` + `check_quality.py`

### Agent 调用方式

在 OpenCode 中使用 `@` 语法调用特定 Agent：

```
@collector 采集今天的 GitHub Trending 数据
@analyzer 分析 knowledge/raw/github-trending-2026-05-01.json
@organizer 整理今天所有已分析的原始数据
```

也可以直接运行流水线：

```bash
python3 pipeline/pipeline.py --sources github,rss --limit 20
```

### 错误处理
- 网络请求失败时，记录错误并跳过该条目，不中断整体流程
- API 限流时，等待后重试，最多 3 次
- 数据格式异常时，写入 `knowledge/raw/errors-{date}.json` 供人工排查

## CLI 命令参考

所有命令均需在项目根目录执行，并确保 `.env` 已配置。

### 流水线主控 (`pipeline/pipeline.py`)

```bash
# 完整四步流水线（采集 + 分析 + 整理 + 保存）
python3 pipeline/pipeline.py --sources github,rss --limit 20

# 仅采集 GitHub，不调用 LLM
python3 pipeline/pipeline.py --sources github --limit 5 --dry-run

# 只执行 Step 1 和 Step 2（采集 + 分析）
python3 pipeline/pipeline.py --sources github --limit 10 --step 1 --step 2

# 切换 LLM 提供商（默认 qwen，覆盖环境变量 LLM_PROVIDER）
python3 pipeline/pipeline.py --sources rss --limit 5 --provider openai

# 显示详细日志
python3 pipeline/pipeline.py --sources github --limit 5 --verbose
```

### RSS 调试 (`pipeline/rss_reader.py`)

```bash
# 独立运行 RSS 采集，查看前 5 条
python3 pipeline/rss_reader.py --limit 10

# 采集并保存到文件
python3 pipeline/rss_reader.py --limit 20 --output /tmp/rss_debug.json
```

### LLM 客户端测试 (`pipeline/model_client.py`)

```bash
# 测试当前配置的 LLM 提供商连通性
python3 pipeline/model_client.py
# 输出示例: 回复: AI Agent 是一种能够自主感知环境、做出决策并执行动作的智能系统。
```

### 质量门控脚本 (`hooks/`)

```bash
# 使用仓库内示例条目（无本地采集数据时）
python3 hooks/validate_json.py tests/fixtures/articles/example-published.json
python3 hooks/check_quality.py tests/fixtures/articles/example-published.json

# 有本地流水线产出时
python3 hooks/validate_json.py knowledge/articles/*.json
python3 hooks/check_quality.py knowledge/articles/*.json
```

### 测试

```bash
# 运行全部测试（推荐）
uv run pytest -q

# 运行指定测试文件
uv run pytest tests/test_model_client.py -q

# 显示详细输出
uv run pytest -v
```

### MCP Server (`mcp_knowledge_server.py`)

零外部依赖的 MCP Server，让 AI 工具可以直接搜索和查询本地知识库。

**提供的工具**：

| 工具名 | 参数 | 功能 |
|--------|------|------|
| `search_articles` | `keyword` (必填), `limit` (可选，默认 5) | 按关键词搜索文章标题和摘要 |
| `get_article` | `article_id` (必填) | 按 ID 获取文章完整信息 |
| `knowledge_stats` | 无 | 返回文章总数、来源分布、热门标签 |

**协议**：JSON-RPC 2.0 over stdio，支持 MCP `initialize`、`tools/list`、`tools/call` 方法。

**三种 AI 工具的 MCP 配置文件**：

| 文件 | 适用工具 |
|------|----------|
| `opencode.json` | OpenCode（`"type":"local"` + array `command` 格式） |
| `.claude/mcp.json` | Claude Code（`mcpServers` 格式） |
| `.codex/mcp.json` | Codex（`mcpServers` 格式） |

重启对应工具后自动加载，即可在对话中调用这三个知识库工具。

## 技术栈
- **运行时**：Python 3.12+ (uv 管理依赖)
- **流水线框架**：纯 Python 四步脚本（pipeline/）
- **数据源**：GitHub Search API v3、RSS（feedparser）、Hacker News API (Algolia)、arXiv API
- **LLM 客户端**：DeepSeek / Qwen (DashScope) / OpenAI，统一 OpenAI-compatible 接口
- **输出格式**：JSON
- **版本管理**：Git
- **测试**：pytest
- **Hooks**：OpenCode TypeScript 插件 + Python 校验脚本
- **MCP**：`mcp_knowledge_server.py`（Python stdlib only）
