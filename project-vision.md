# AI 知识库 · 项目愿景 v0.2

> Last updated: 2026-10-04
> v0.1（2026-04-28）的技术描述已被取代；本版按 ticket 17 与 Horizon/SQLite 切换后的现实重写（当前版本 `0.7.0`，切换后的变更记录见 `CHANGELOG.md` §Unreleased）。历史意图源见 `docs/product/ai-kb/product.html` 的变更记录。

## 要做什么

- 采集编排（固定 Horizon 采集、定时调度与简报）由 Information Assistant 负责；通用 Horizon 通信与设置由 agent-tools 提供（RSS / GitHub 等源由 Horizon `data/config.json` 管理）
- 采集结果以完成的 provider payload 交给本仓：`kb.ingest.ingest_horizon_payload` 完成 **映射 → admission → 记账 → 入库**，写入规范化 SQLite 资产库 `knowledge/kb.sqlite`
- 逐条 admission 是确定性的、可审计的（accept / reject / fail 均记录原因码与运行记账）
- 规范库支撑 FTS5 检索、导出/备份，以及三个只读消费面：Flask UI、MCP server、每日 EN / zh-CN 简报（SMTP/webhook 投递，未配置时如实报告 `missing_config`）

## 不做什么

- 不再运行任何 legacy JSON 管线（LangGraph `workflows/`、`hooks/`、`prompts/` 已在 ticket 16 退役，不要重建）
- 不做知识条目之间的自动关联（`edges` 表已预留，图谱增量未立项）
- 不做多用户 / SaaS / 新前端框架
- 不引入语义/向量检索，除非关键词/结构化检索未通过明确的产品验收

## 边界 & 验收

- **连续跑通**：由 Information Assistant 定时触发，连续 7 天自动采集与接纳跑完无报错
- **记账诚实**：每次运行对每条候选给出可解释的 admission 结果；部分失败/失败非零退出
- **两周 go/no-go 精神延续**：以「我是否信任知识库的回答」为准，而非条目数量

## 怎么验证

最终检验：当我需要回答“最近有哪些值得关注的 AI repo / RAG 框架 / Agent 工具”时，我信任自己的知识库（UI 检索 / MCP / 每日简报）给出的答案，而不是重新去 GitHub/推特翻一遍。
