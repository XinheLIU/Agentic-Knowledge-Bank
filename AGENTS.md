# AGENTS.md — AI 知识库项目

> Last updated: 2026-05-06
> 本文件是项目的长期记忆，描述当前版本 `0.5.0` 的真实结构与运行方式。

## 项目定义

**AI Knowledge Base（AI 知识库）** 是一个自动化技术情报收集与分析系统。
当前版本使用 LangGraph 将采集、分析、审核、修订、整理显式建模为有状态工作流，
将分散的 AI/LLM/Agent 资讯转成结构化 JSON 知识条目。

### 核心价值
- 每日自动采集 AI/LLM/Agent 领域的高质量 GitHub 与 RSS 内容
- 通过显式工作流完成 **规划 → 采集 → 分析 → 审核 → 修订 → 入库**
- 输出统一 JSON 知识条目，便于检索与下游消费
- 写入知识条目时自动触发 JSON 校验与质量评分

## 项目结构

```text
ai-kb/
├── AGENTS.md                          # 项目记忆文件（本文件）
├── project-vision.md                  # 项目愿景与 go/no-go 验收标准
├── TODO.md                            # 待办事项（可能含用户未完成编辑）
├── pyproject.toml                     # Python 依赖与工具配置
├── .env.example                       # 环境变量模板
├── .github/workflows/daily-collect.yml
├── .opencode/
│   ├── agents/
│   ├── skills/
│   └── plugins/validate.ts            # OpenCode 写入钩子：自动校验 + 质量评分
├── workflows/
│   ├── graph.py                       # LangGraph 图定义与 CLI
│   ├── state.py                       # 工作流状态定义
│   ├── planner.py                     # 节点 ① 动态规划策略
│   ├── collector.py                   # 节点 ② GitHub + RSS 采集
│   ├── analyzer.py                    # 节点 ③ 单条 LLM 分析
│   ├── reviewer.py                    # 节点 ④ 五维加权审核
│   ├── reviser.py                     # 节点 ⑤ 根据反馈定向修订
│   ├── organizer.py                   # 节点 ⑥ 整理入库
│   ├── human_flag.py                  # 节点 ⑦ 人工介入终点
│   ├── model_client.py                # OpenAI-compatible LLM 客户端
│   └── rss_sources.yaml               # RSS 源配置
├── patterns/
│   ├── router.py                      # Router 模式示例
│   └── supervisor.py                  # Supervisor 模式示例
├── hooks/
│   ├── validate_json.py               # JSON Schema 校验
│   └── check_quality.py               # 五维度质量评分
├── tests/                             # pytest 测试套件
├── notebooks/
│   └── langgraph_workflow_demo.ipynb  # 新工作流演示 notebook
├── spec/
│   ├── requirements.md
│   ├── tech-spec.md
│   ├── hooks-spec.md
│   ├── testing-strategy.md
│   ├── upgrade-0.4.0-to-0.5.0.md
│   └── keywords-v0.1.txt
├── knowledge/
│   ├── raw/
│   ├── articles/
│   └── pending_review/
├── mcp_knowledge_server.py            # MCP Server：知识库搜索
├── opencode.json
├── .claude/mcp.json
└── .codex/mcp.json
```

## 编码规范

### 文件命名
- 知识条目：`knowledge/articles/{source_slug}-{YYYYMMDD}-{NNN}.json`
  - 例：`knowledge/articles/github-20260506-001.json`
  - 例：`knowledge/articles/rss-openai-blog-20260506-001.json`
- 索引文件：`knowledge/articles/index.json`
- 待人工审核：`knowledge/pending_review/pending-{YYYYMMDD-HHMMSS}.json`
- **版本库**：`knowledge/raw/` 与 `knowledge/articles/` 中的 JSON 由自动流程产出；格式与质量手动校验使用 `tests/fixtures/articles/example-published.json`。

### JSON 格式
- 使用 2 空格缩进
- 日期格式：ISO 8601
- 字符编码：UTF-8
- 文章必须满足 hook 约束：`id`, `title`, `source_url`, `summary`, `tags`, `status`
- 常见附加字段：`source`, `url`, `collected_at`, `score`, `audience`, `relevance_score`, `category`, `key_insight`

### 语言约定
- 代码、JSON 键名、文件名：英文
- 摘要、分析、注释：中文
- 标签：英文小写，优先使用质量脚本认可的标准标签

## 工作流规则

### LangGraph 节点图

```text
plan -> collect -> analyze -> review
                             | pass -> organize -> END
                             | fail & iteration < max -> revise -> review
                             | fail & iteration >= max -> human_flag -> END
```

### Agent 协作规则
1. **单向数据流**：Planner → Collector → Analyzer → Reviewer → Reviser/Organizer/HumanFlag
2. **职责隔离**：每个节点只修改自己负责的状态字段
3. **幂等性**：Organizer 以 `source_url` 去重，避免重复文章
4. **质量门控**：Reviewer 用代码重算五维加权分；未通过且达到上限则进入 `pending_review/`
5. **可追溯**：每个条目保留 `source_url` 与 `collected_at`
6. **自动校验**：写入 `knowledge/articles/*.json` 时自动运行 `validate_json.py` + `check_quality.py`

### CLI 命令

所有命令均需在项目根目录执行，并确保 `.env` 已配置。

```bash
# 完整 LangGraph 工作流
uv run python -m workflows.graph --sources github,rss --limit 20

# 仅采集 GitHub，跳过落盘
uv run python -m workflows.graph --sources github --limit 5 --dry-run

# 切换 LLM 提供商
uv run python -m workflows.graph --sources rss --limit 5 --provider openai

# 显示详细日志
uv run python -m workflows.graph --sources github,rss --limit 10 --verbose

# 在自动化中将 human_flag 视为失败
uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag

# Non-LLM 测试
uv run pytest -q -m non_llm

# Real-LLM 端到端验证
uv run pytest -q -m llm_e2e
```

### 错误处理
- 网络请求失败时记录错误并继续，不中断整批流程
- LLM 调用失败时节点降级：Analyzer 生成低分草稿，Reviewer 自动放行避免阻塞，Reviser 保留原结果
- 审核循环超过上限时，写入 `knowledge/pending_review/`，不污染 `knowledge/articles/`

## 自动化规则
- GitHub Actions 每日执行 `uv run python -m workflows.graph --sources github,rss --limit 20 --fail-on-human-flag`
- 自动化环境中，`HumanFlag` 是失败信号，不是正常产物
- 定时工作流只提交 `knowledge/articles/` 和 `knowledge/raw/`，不提交 `knowledge/pending_review/`
- 测试工作流与生产采集工作流分离：真实 LLM 验证使用独立 `.github/workflows/llm-e2e.yml`

## 技术栈
- **运行时**：Python 3.12+（uv 管理依赖）
- **工作流框架**：LangGraph
- **数据源**：GitHub Search API v3、RSS（feedparser）
- **LLM 客户端**：DeepSeek / Qwen / OpenAI，统一 OpenAI-compatible HTTP 接口
- **输出格式**：JSON
- **测试**：pytest
- **Hooks**：OpenCode TypeScript 插件 + Python 校验脚本
- **MCP**：`mcp_knowledge_server.py`（Python stdlib only）

## 实施约束
- `pipeline/` 与 `scripts/` 已移除，不支持旧入口
- `TODO.md` 可能包含用户手工编辑，除非任务明确要求，不要顺手改动
- `patterns/` 是演示代码，不是生产入口，但应保持可导入
