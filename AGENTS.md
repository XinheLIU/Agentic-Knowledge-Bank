# AGENTS.md — AI 知识库项目

> Last updated: 2026-06-23
> 本文件是项目的长期记忆，描述当前版本 `0.7.0` 的真实结构与运行方式。

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
│   ├── analyzer.py                    # 节点 ③ 单条 LLM 分析（含个人相关性评分）
│   ├── reviewer.py                    # 节点 ④ 个人相关性加权审核
│   ├── reviser.py                     # 节点 ⑤ 根据反馈定向修订
│   ├── organizer.py                   # 节点 ⑥ 整理入库
│   ├── human_flag.py                  # 节点 ⑦ 人工介入终点
│   ├── model_client.py                # OpenAI-compatible LLM 客户端
│   ├── prompts.py                     # Prompt 模板加载器（提供商覆盖 → 通用回退）
│   ├── digest.py                      # 每日简报生成 + 邮件发送（独立 CLI）
│   ├── relevance_profile.py           # 个人相关性配置加载器
│   ├── relevance_profile.yaml         # 默认个人相关性配置
│   └── rss_sources.yaml               # RSS 源配置
├── prompts/                           # 外置 Prompt 模板（analyzer/reviewer/reviser + system）
├── patterns/
│   ├── router.py                      # Router 模式示例
│   └── supervisor.py                  # Supervisor 模式示例
├── hooks/
│   ├── validate_json.py               # JSON Schema 校验
│   └── check_quality.py               # 六维度质量评分
├── tests/                             # pytest 测试套件
├── notebooks/
│   └── langgraph_workflow_demo.ipynb  # 新工作流演示 notebook
├── docs/archive/                      # 历史审计与策略备忘（见 docs/archive/README.md）
├── knowledge/
│   ├── raw/
│   ├── articles/
│   └── pending_review/
├── ui/                                # Notion-like 知识库管理面板
│   ├── app.py                         # Flask API + Article 模型
│   ├── static/
│   │   ├── index.html                 # SPA 入口
│   │   ├── css/style.css              # Notion 风格样式
│   │   └── js/app.js                  # 前端逻辑
│   └── requirements.txt               # Flask + flask-cors
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
- 个人相关性字段（v0.6.0 新增）：`personal_fit_score`, `technical_depth_score`, `actionability_score`, `source_credibility_score`, `novelty_score`, `priority_score`, `reading_priority`, `relevance_reason`, `suggested_action`, `confidence`, `source_type`, `learning_track`, `learning_tags`
- 学习标签允许列表：`agent-harness`, `langgraph`, `langchain`, `data-agent`, `mcp`, `tool-use`, `browser-agent`, `computer-use`, `evaluation`, `repo-tutorial`, `reference-architecture`, `paper-to-code`, `production-rag`, `local-llm`, `quant-ai`, `business-context`, `implementation-pattern`, `architecture-reference`, `production-lesson`, `research-method`, `noise`

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
4. **per_source_limit + 比例缩放**：RSS 采集时，每个源在 `rss_sources.yaml` 中配置 `per_source_limit`（默认 5）；当总和超过全局 limit 时，按比例缩放，每个源至少保留 1 条
5. **fingerprint 去重**：Collector 在采集 RSS 时，会计算 `fingerprint = normalize(title) + "|" + domain(url)`，在内存去重的同时，也会排除 `knowledge/articles/` 中已有的相同 fingerprint 条目
6. **质量门控**：Reviewer 用代码重算个人相关性加权分；未通过且达到上限则进入 `pending_review/`
7. **可追溯**：每个条目保留 `source_url` 与 `collected_at`
8. **自动校验**：写入 `knowledge/articles/*.json` 时自动运行 `validate_json.py` + `check_quality.py`

### 个人相关性评分体系（v0.6.0）

**配置**：`workflows/relevance_profile.yaml` 定义用户学习画像，包含：
- `user_status`：用户当前状态描述
- `focus_topics`：三级优先主题（P0 必学、P1 有价值上下文、P2 背景）
- `learning_tracks`：学习路线分类
- `preferred_source_types`：来源类型偏好（高/中/低）
- `learning_tag_allowlist`：学习标签允许列表
- `negative_patterns`：噪音模式

**评分字段**：
| 字段 | 范围 | 含义 |
|------|------|------|
| `personal_fit_score` | 0.0-1.0 | 与用户学习路线的匹配度 |
| `technical_depth_score` | 0.0-1.0 | 技术深度 |
| `actionability_score` | 0.0-1.0 | 学习行动价值 |
| `source_credibility_score` | 0.0-1.0 | 来源可信度 |
| `novelty_score` | 0.0-1.0 | 新颖度 |
| `priority_score` | 0-100 | 加权综合优先级 |
| `reading_priority` | enum | `study-now`, `save-for-context`, `skim`, `low-priority`, `skip` |
| `confidence` | 0.0-1.0 | 评分置信度 |
| `source_type` | enum | `repository`, `paper`, `blog`, `discussion`, `benchmark`, `tutorial`, `product`, `news`, `documentation`, `unknown` |
| `learning_track` | enum | 学习路线归属 |
| `learning_tags` | list | 学习意图标签，从允许列表选取 |

**规则约束**：
- `relevance_score` 兼容字段，镜像 `personal_fit_score`
- `score` 兼容字段（1-10），从 `priority_score` 派生
- 泛泛讨论/新闻无技术机制信号时，`reading_priority` 最多为 `low-priority`
- P0 匹配且有教程/参考架构价值时，`reading_priority` 至少为 `save-for-context`
- `skip` 仅用于明确无关、重复、损坏或低质量条目；不确定条目用 `low-priority`
- 缺失或部分配置时自动回退到内置默认值

**质量评分（v0.6.0）**：6 维度共 115 分
1. 摘要质量 (25)
2. 技术深度 (25) — 优先使用 `personal_fit_score` + `technical_depth_score`
3. 格式规范 (20)
4. 标签精度 (15) — 宽标签 + 学习标签分别评分
5. 空洞词检测 (15)
6. 个人相关性 (15) — 奖励 `reading_priority`, `relevance_reason`, `suggested_action`, `source_type`, `learning_track`, `personal_fit_score`

等级：A (>=90), B (>=70), C (<70)

### Prompt 模板（v0.7.0）

- LLM prompt 文本外置到 `prompts/*.txt`，不再内联在节点里：`analyzer.txt`、`reviewer.txt`、`reviewer_system.txt`、`reviser.txt`、`reviser_system.txt`。
- 加载器 `workflows/prompts.py`：`load_prompt(name, provider)` 先找 `prompts/<provider>/<name>.txt`，回退到 `prompts/<name>.txt`；`render(name, mapping)` 用 `string.Template`（`$placeholder`）填充，因模板含大量字面 JSON `{}`，不可用 `str.format`。
- 迁移时 prompt 文本逐字提取，行为与 v0.6.0 一致。新增 provider 专属变体只需放入 `prompts/<provider>/`。

### 信息简报推送（digest，v0.7.0）

- `workflows/digest.py` 是独立 CLI（非图节点），在运行后读取 `knowledge/articles/`，筛选当日 `study-now` / `save-for-context` 条目，按 `priority_score` 排序、分组渲染 markdown 并发邮件。
- SMTP 配置走环境变量：`EMAIL_ADDRESS`、`EMAIL_PASSWORD`、`SMTP_HOST`(默认 smtp.gmail.com)、`SMTP_PORT`(默认 587)、`DIGEST_RECIPIENTS`。未配置时打印简报并以 0 退出（优雅跳过）。
- 仅用标准库 `smtplib`/`email`，无新增依赖。机制借鉴自已退役的 Info-Sentinel-Agent。

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

# 预览/发送每日简报（未配置 SMTP 时仅打印）
uv run python -m workflows.digest --stdout
uv run python -m workflows.digest --since 2026-06-23

# Real-LLM 端到端验证
uv run pytest -q -m llm_e2e

# 启动知识库管理 UI（本地浏览 http://localhost:5050）
# UI 提供来源管理视图，可查看所有 RSS 源、近 7 天采集数，以及启用/禁用源
uv run python ui/app.py
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
- **UI**：Flask + Vanilla JS/CSS，Notion-like 管理面板

## 实施约束
- `pipeline/` 与 `scripts/` 已移除，不支持旧入口
- `TODO.md` 可能包含用户手工编辑，除非任务明确要求，不要顺手改动
- `patterns/` 是演示代码，不是生产入口，但应保持可导入
