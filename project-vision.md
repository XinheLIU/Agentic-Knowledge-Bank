# AI 知识库 · 项目愿景 v0.1
> Last updated: 2026-04-28

## 要做什么
- 每天抓取 GitHub Trending 当天数据（4–5 个语言分类，约 125 条原始输入）
- 用关键词硬筛出最多 20 条 AI 相关 repo，再用 LLM Agent 分析其 README
- 输出 Markdown 知识条目（YAML frontmatter + 自然语言正文），写入 Obsidian inbox
- 由我手动 review、打 quality 分、修正标签，再归拢到 knowledge/ 或 archive/

## 不做什么
- 不做历史回溯（GitHub Trending 无历史 API，从当天开始冷启动积累）
- 不做知识条目之间的自动关联（先不建图谱）
- 不做实时推送 / 多用户 / Web UI
- 不做代码级分析（只读 README + 元数据）

## 边界 & 验收
- **连续跑通**：本地定时触发，连续 7 天自动跑完 pipeline 无报错
- **两周 go/no-go**：
  - knowledge/ 中 `user_quality >= 2` 的条目 >= 60 条
  - 我至少在 4 个不同的天主动打开 Obsidian 看了 inbox
  - keywords.txt 至少迭代过 1 次
- **不满足 = 项目关停**

## 怎么验证
最终检验：当我需要回答“最近有哪些值得关注的 AI repo / RAG 框架 / Agent 工具”时，我信任自己的知识库给出的答案，而不是重新去 GitHub/推特翻一遍。
