---
name: markdown-writer
description: >
  将结构化分析结果写入 Markdown 文件（YAML frontmatter + Markdown 正文）。
  由 @organizer Agent 调用。
---

# Markdown 写入技能

## 输入
- `entry`: 完整条目对象（含 frontmatter 字段和 analysis_content）
- `output_dir`: 输出目录（默认 `knowledge/articles/`）
- `filename`: 文件名（如 `2026-04-29-owner-repo.md`）

## 输出
写入到指定路径的 Markdown 文件。

## YAML frontmatter 模板

```yaml
---
id: "{id}"
title: "{title}"
source_url: "{url}"
summary: "{agent_summary}"
tags: {agent_tags}
status: "inbox"
fetched_at: "{collected_at}"
trending_date: "{date}"
language: "{language}"
stars: {stars}
stars_today: {stars_today}
agent_category: "{agent_category}"
agent_tags: {agent_tags}
user_tags: []
user_quality: 0
user_notes: ""
relevance_score: {relevance_score}
source: "{source}"
---
```

## 正文模板

```markdown
## 分析

{analysis_content}
```

## 规则
- 使用 UTF-8 编码
- YAML 值含特殊字符时加引号
- 不覆盖已存在的 `user_*` 字段（写入时初始化为默认值）
- 同一天同一 id 重复写入应覆盖旧文件

## 错误处理
- 目录不存在 → 自动创建
- 写入失败 → 抛出异常，由 Organizer Agent 捕获并记录
